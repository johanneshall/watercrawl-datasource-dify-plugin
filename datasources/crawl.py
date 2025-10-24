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

            # Initialize and yield initial status
            crawl_res = WebSiteInfo(
                web_info_list=[],
                status="processing",
                total=crawl_request['options']['spider_options']['page_limit'],
                completed=0
            )
            yield self.create_crawl_message(crawl_res)
            
            # Monitor crawl progress with retries and live counting
            seen_urls = set()
            consecutive_failures = 0
            max_consecutive_failures = 3
            monitoring_completed = False
            
            while consecutive_failures < max_consecutive_failures:
                try:
                    for event in client.monitor_crawl_request(crawl_request['uuid'], download=False):
                        event_type = event.get('type')
                        
                        # Reset failure count on successful event
                        consecutive_failures = 0
                        
                        # Track progress with deduplication
                        if event_type == 'result':
                            result_url = event.get('data', {}).get('url')
                            if result_url and result_url not in seen_urls:
                                seen_urls.add(result_url)
                                crawl_res.completed = len(seen_urls)
                                yield self.create_crawl_message(crawl_res)
                        
                        # Check for completion
                        elif event_type == 'state':
                            status = event.get('data', {}).get('status')
                            if status in ['finished', 'failed', 'canceled']:
                                monitoring_completed = True
                                break
                    
                    # If we got the completion state, break out of retry loop
                    if monitoring_completed:
                        break
                    
                    # Monitoring stream ended without completion state
                    # This shouldn't happen normally, so break and fetch results
                    break
                    
                except (ChunkedEncodingError, ConnectionError, Timeout, RequestException):
                    consecutive_failures += 1
                    if consecutive_failures < max_consecutive_failures:
                        # Wait before retrying with exponential backoff
                        time.sleep(2 * consecutive_failures)
                        continue
                    # Max consecutive failures reached, will fetch results below
                    break
            
            # Fetch and yield final results exactly once
            yield from self._fetch_and_yield_final_results(
                client, crawl_request['uuid'], crawl_res
            )

        except ToolProviderCredentialValidationError:
            # Re-raise credential errors without modification
            raise
        except ValueError as e:
            # Re-raise validation errors
            raise
        except Exception as e:
            # Catch any other unexpected errors
            raise ValueError(f"Failed to crawl website: {str(e)}")

    def _fetch_and_yield_final_results(
        self, client: WaterCrawlAPIClient, crawl_uuid: str, crawl_res: WebSiteInfo
    ) -> Generator[WebsiteCrawlMessage, None, None]:
        """Fetch all results from API and yield final completion message."""
        try:
            all_results = []
            page = 1
            
            while True:
                # Fetch results with download=True to get embedded result objects
                results_response = client.get_crawl_request_results(
                    crawl_uuid, 
                    page=page, 
                    page_size=100,
                    download=True
                )
                
                if not results_response:
                    break
                
                # Get results from this page
                results = results_response.get('results', [])
                if not results:
                    break
                
                # Process all results from this page
                for result_data in results:
                    all_results.append(self._process_result(result_data))
                
                # Check if there's a next page using the 'next' field
                # This is the standard Django REST pagination pattern
                if not results_response.get('next'):
                    break
                    
                page += 1
            
            # Yield final completion message with all results
            crawl_res.status = "completed"
            crawl_res.web_info_list = all_results
            crawl_res.completed = len(all_results)
            crawl_res.total = len(all_results)
            yield self.create_crawl_message(crawl_res)
            
        except Exception as e:
            # On API failure, return empty completion
            crawl_res.status = "completed"
            crawl_res.web_info_list = []
            yield self.create_crawl_message(crawl_res)

    @staticmethod
    def _process_result(data):
        result = data.get("result", {})
        metadata = result.get("metadata", {})
        return WebSiteInfoDetail(
            source_url=data["url"],
            content=result.get("markdown", "") or "",
            title=metadata.get("title", "") or metadata.get("og:title", "") or "",
            description=metadata.get('description') or metadata.get('og:description') or ""
        )