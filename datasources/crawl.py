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

            # Initialize and yield initial status
            crawl_res = WebSiteInfo(
                web_info_list=[],
                status="processing",
                total=crawl_request['options']['spider_options']['page_limit'],
                completed=0
            )
            yield self.create_crawl_message(crawl_res)
            
            # Monitor crawl progress with retries
            for attempt in range(3):
                try:
                    for event in client.monitor_crawl_request(crawl_request['uuid'], download=False):
                        event_type = event.get('type')
                        
                        # Track and report progress on each result
                        if event_type == 'result':
                            crawl_res.completed += 1
                            yield self.create_crawl_message(crawl_res)
                        
                        # Check for completion
                        elif event_type == 'state':
                            status = event.get('data', {}).get('status')
                            if status in ['completed', 'failed', 'stopped']:
                                # Fetch and yield final results
                                yield from self._fetch_and_yield_final_results(
                                    client, crawl_request['uuid'], crawl_res
                                )
                                return
                    
                    # Monitoring completed without state event
                    break
                    
                except (ChunkedEncodingError, ConnectionError, Timeout, RequestException):
                    if attempt < 2:  # Retry
                        time.sleep(2 * (attempt + 1))
                        continue
                    # Final attempt failed, fetch results anyway
                    break
            
            # Fetch final results from API (either after successful monitoring or retry failure)
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
                results_response = client.get_crawl_request_results(
                    crawl_uuid, 
                    page=page, 
                    page_size=100,
                    download=True
                )
                
                if not results_response or not results_response.get('results'):
                    break
                
                for result_data in results_response['results']:
                    all_results.append(self._process_result(result_data))
                
                if page >= results_response.get('total_pages', 1):
                    break
                page += 1
            
            # Yield final completion message with all results
            crawl_res.status = "completed"
            crawl_res.web_info_list = all_results
            crawl_res.completed = len(all_results)
            crawl_res.total = len(all_results)
            yield self.create_crawl_message(crawl_res)
            
        except Exception:
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
            title=metadata.get("title", "") or metadata.get( "og:title", "") or "",
            description=metadata.get('description') or metadata.get('og:description') or ""
        )
