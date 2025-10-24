import time
from collections.abc import Generator
from typing import Any, Mapping

from dify_plugin.entities.datasource import (
    WebSiteInfo,
    WebSiteInfoDetail,
    WebsiteCrawlMessage,
)
from dify_plugin.interfaces.datasource.website import WebsiteCrawlDatasource
from dify_plugin.errors.tool import ToolProviderCredentialValidationError
from requests.exceptions import (
    ChunkedEncodingError,
    ConnectionError,
    Timeout,
    RequestException
)
from watercrawl import WaterCrawlAPIClient


class CrawlDatasource(WebsiteCrawlDatasource):
    def _get_website_crawl(
            self, datasource_parameters: Mapping[str, Any]
    ) -> Generator[WebsiteCrawlMessage, None, None]:
        """
        WaterCrawl datasource implementation.
        API docs: https://docs.watercrawl.dev
        """
        source_url = datasource_parameters.get("url")
        if not source_url:
            raise ValueError("Url is required")

        if not self.runtime.credentials.get("api_key"):
            raise ToolProviderCredentialValidationError("api key is required")

        try:
            client = WaterCrawlAPIClient(
                api_key=self.runtime.credentials.get("api_key"),
                base_url=self.runtime.credentials.get("base_url")
                         or "https://app.watercrawl.dev",
            )

            # Parse comma-separated list parameters
            exclude_paths_param = datasource_parameters.get("exclude_paths")
            exclude_paths = exclude_paths_param.split(",") if exclude_paths_param else []
            
            include_paths_param = datasource_parameters.get("include_paths")
            include_paths = include_paths_param.split(",") if include_paths_param else []
            
            allowed_domains_param = datasource_parameters.get("allowed_domains")
            allowed_domains = allowed_domains_param.split(",") if allowed_domains_param else []
            
            exclude_tags_param = datasource_parameters.get("exclude_tags")
            exclude_tags = exclude_tags_param.split(",") if exclude_tags_param else []
            
            include_tags_param = datasource_parameters.get("include_tags")
            include_tags = include_tags_param.split(",") if include_tags_param else []

            # Parse extra_headers JSON if provided
            import json
            extra_headers = {}
            extra_headers_param = datasource_parameters.get("extra_headers")
            if extra_headers_param:
                try:
                    extra_headers = json.loads(extra_headers_param)
                except json.JSONDecodeError:
                    raise ValueError("extra_headers must be valid JSON")

            # Build spider options
            spider_options = {
                "max_depth": datasource_parameters.get("max_depth") or 1,
                "page_limit": datasource_parameters.get("limit") or 1,
                "exclude_paths": exclude_paths,
                "include_paths": include_paths,
            }
            if allowed_domains:
                spider_options["allowed_domains"] = allowed_domains
            if datasource_parameters.get("proxy_server_slug"):
                spider_options["proxy_server"] = datasource_parameters.get("proxy_server_slug")

            # Build page options
            page_options = {
                "only_main_content": datasource_parameters.get("only_main_content", True),
                "ignore_rendering": datasource_parameters.get("ignore_rendering", False),
            }
            if exclude_tags:
                page_options["exclude_tags"] = exclude_tags
            if include_tags:
                page_options["include_tags"] = include_tags
            if datasource_parameters.get("locale"):
                page_options["locale"] = datasource_parameters.get("locale")
            if extra_headers:
                page_options["extra_headers"] = extra_headers

            # Create crawl request
            crawl_request = client.create_crawl_request(
                url=source_url,
                spider_options=spider_options,
                page_options=page_options
            )

            # Get expected total from page_limit (FIXED - set once)
            expected_total = crawl_request['options']['spider_options']['page_limit']
            
            # Initialize crawl result
            crawl_res = WebSiteInfo(
                web_info_list=[],
                status="processing",
                total=expected_total,  # Fixed value, never changed
                completed=0
            )
            yield self.create_crawl_message(crawl_res)
            
            # Cache for results as they come in
            all_results = []
            seen_urls = set()
            consecutive_failures = 0
            max_consecutive_failures = 3
            
            while consecutive_failures < max_consecutive_failures:
                try:
                    # Monitor with download=True to get full content as it streams
                    for event in client.monitor_crawl_request(crawl_request['uuid'], download=True):
                        event_type = event.get('type')
                        
                        # Reset failure count on successful event
                        consecutive_failures = 0
                        
                        if event_type == 'result':
                            # Process and cache result
                            result_data = event.get('data', {})
                            result_url = result_data.get('url')
                            
                            # Deduplicate by URL
                            if result_url and result_url not in seen_urls:
                                seen_urls.add(result_url)
                                processed = self._process_result(result_data)
                                all_results.append(processed)
                                
                                # KEY FIX: Send cumulative results (Tavily pattern)
                                # This ensures Dify gets the data incrementally
                                crawl_res.completed = len(all_results)
                                crawl_res.web_info_list = all_results.copy()  # Send ALL results so far
                                crawl_res.status = "processing"
                                # Keep total fixed
                                yield self.create_crawl_message(crawl_res)
                        
                        elif event_type == 'state':
                            status = event.get('data', {}).get('status')
                            # DON'T update total from state
                            
                            if status in ['finished', 'failed', 'canceled']:
                                # Final completion message
                                crawl_res.status = "completed"
                                crawl_res.web_info_list = all_results
                                crawl_res.completed = len(all_results)
                                crawl_res.total = len(all_results)  # Update total to actual count at end
                                yield self.create_crawl_message(crawl_res)
                                return
                    
                    # Monitoring completed successfully
                    break
                    
                except (ChunkedEncodingError, ConnectionError, Timeout, RequestException):
                    consecutive_failures += 1
                    if consecutive_failures < max_consecutive_failures:
                        time.sleep(2 * consecutive_failures)
                        continue
                    break
            
            # Final message if monitoring ended without explicit completion
            crawl_res.status = "completed"
            crawl_res.web_info_list = all_results
            crawl_res.completed = len(all_results)
            crawl_res.total = len(all_results)  # Update total to actual count at end
            yield self.create_crawl_message(crawl_res)

        except ToolProviderCredentialValidationError:
            raise
        except ValueError as e:
            raise
        except Exception as e:
            raise ValueError(f"Failed to crawl website: {str(e)}")

    @staticmethod
    def _process_result(data):
        """Process a single crawl result with content truncation."""
        result = data.get("result", {})
        
        # Debug: Check what we're getting
        if isinstance(result, str):
            # Result is a URL string - this shouldn't happen with download=True
            # But handle it gracefully
            return WebSiteInfoDetail(
                source_url=data.get("url", ""),
                content=f"[Error: Result was a URL instead of content object: {result}]",
                title="",
                description=""
            )
        
        if not isinstance(result, dict):
            # Unexpected result type
            return WebSiteInfoDetail(
                source_url=data.get("url", ""),
                content=f"[Error: Unexpected result type: {type(result)}]",
                title="",
                description=""
            )
        
        # Extract metadata and content
        metadata = result.get("metadata", {})
        content = result.get("markdown", "") or result.get("content", "") or ""
        
        # Ensure we have some content
        if not content:
            content = "[No content available]"
        
        # Truncate extremely large content to prevent buffer overflow
        max_content_length = 100000  # 100KB per page (more generous with increased buffer)
        if len(content) > max_content_length:
            content = content[:max_content_length] + "\n\n[Content truncated due to size...]"
        
        title = metadata.get("title", "") or metadata.get("og:title", "") or ""
        description = metadata.get("description", "") or metadata.get("og:description", "") or ""
        
        return WebSiteInfoDetail(
            source_url=data.get("url", ""),
            content=content,
            title=title,
            description=description
        )