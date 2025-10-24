import time
import json
from collections.abc import Generator
from typing import Any, Mapping

from dify_plugin.entities.datasource import (
    WebSiteInfo,
    WebSiteInfoDetail,
    WebsiteCrawlMessage,
)
from dify_plugin.interfaces.datasource.website import WebsiteCrawlDatasource
from dify_plugin.errors.tool import ToolProviderCredentialValidationError
from requests import HTTPError
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
        the api doc:
        https://docs.watercrawl.dev
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

            crawl_request = client.create_crawl_request(
                url=source_url,
                spider_options=spider_options,
                page_options=page_options
            )

            # Track progress
            completed_count = 0
            max_retries = 3
            retry_delay = 2  # seconds
            
            for attempt in range(max_retries):
                try:
                    # Monitor with download=True to get result objects instead of URLs
                    for event in client.monitor_crawl_request(crawl_request['uuid'], download=True):
                        event_type = event.get('type')
                        
                        # Handle state changes
                        if event_type == 'state':
                            state_data = event.get('data', {})
                            status = state_data.get('status')
                            
                            # Check if crawl is completed or failed
                            if status in ['completed', 'failed', 'stopped']:
                                # Send final completion message
                                final_message = WebSiteInfo(
                                    web_info_list=[],
                                    status="completed",
                                    total=crawl_request['options']['spider_options']['page_limit'],
                                    completed=completed_count
                                )
                                yield self.create_crawl_message(final_message)
                                return
                        
                        # Handle result events - yield each result immediately
                        elif event_type == 'result':
                            result_data = event.get('data')
                            if result_data:
                                processed_result = self._process_result(result_data)
                                completed_count += 1
                                
                                # Yield each result individually to avoid buffer overflow
                                result_message = WebSiteInfo(
                                    web_info_list=[processed_result],
                                    status="processing",
                                    total=crawl_request['options']['spider_options']['page_limit'],
                                    completed=completed_count
                                )
                                yield self.create_crawl_message(result_message)
                        
                        # Ignore 'feed' events (engine feedback)
                        elif event_type == 'feed':
                            continue
                    
                    # Successfully completed the monitoring
                    break
                    
                except (ChunkedEncodingError, ConnectionError, Timeout) as e:
                    if attempt < max_retries - 1:
                        # Wait before retrying
                        time.sleep(retry_delay * (attempt + 1))
                        # Continue monitoring from where we left off
                        continue
                    else:
                        # Final attempt failed, return completion with what we have
                        final_message = WebSiteInfo(
                            web_info_list=[],
                            status="completed",
                            total=crawl_request['options']['spider_options']['page_limit'],
                            completed=completed_count
                        )
                        yield self.create_crawl_message(final_message)
                        return
                        
                except RequestException as e:
                    # Other request exceptions - retry with backoff
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (attempt + 1))
                        continue
                    else:
                        # Return completion with partial results
                        final_message = WebSiteInfo(
                            web_info_list=[],
                            status="completed",
                            total=crawl_request['options']['spider_options']['page_limit'],
                            completed=completed_count
                        )
                        yield self.create_crawl_message(final_message)
                        return

            # Fallback if we exit the loop without a state event
            final_message = WebSiteInfo(
                web_info_list=[],
                status="completed",
                total=crawl_request['options']['spider_options']['page_limit'],
                completed=completed_count
            )
            yield self.create_crawl_message(final_message)

        except ToolProviderCredentialValidationError:
            # Re-raise credential errors without modification
            raise
        except ValueError as e:
            # Re-raise validation errors
            raise
        except Exception as e:
            # Catch any other unexpected errors
            raise ValueError(f"Failed to crawl website: {str(e)}")

    @staticmethod
    def _process_result(data):
        result = data.get("result", {})
        metadata = result.get("metadata", {})
        return WebSiteInfoDetail(
            source_url=data["url"],
            content=result.get("markdown", "") or "",
            title=metadata.get("title", "") or metadata.get( "og:title", "") or "",
            description=metadata.get('description') or metadata.get('og:description') or ""
        )
