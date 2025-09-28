from typing import Any, Mapping
from urllib.parse import urlparse

from dify_plugin.errors.tool import ToolProviderCredentialValidationError
from dify_plugin.interfaces.datasource import DatasourceProvider
from requests import HTTPError
from watercrawl import WaterCrawlAPIClient


class WatercrawlDatasourceProvider(DatasourceProvider):
    def _validate_credentials(self, credentials: Mapping[str, Any]) -> None:
        base_url = credentials.get('base_url', None) or 'https://app.watercrawl.dev/'

        if not self.validate_url(base_url):
            raise ToolProviderCredentialValidationError("Invalid base URL")

        try:
            response = WaterCrawlAPIClient(credentials["api_key"], base_url).get_crawl_requests_list(page_size=1)
            if 'results' not in response:
                raise ToolProviderCredentialValidationError("Invalid URL or API key")
        except HTTPError as e:
            if e.response.status_code == 401:
                raise ToolProviderCredentialValidationError("Invalid API key")
            if e.response.status_code == 404:
                raise ToolProviderCredentialValidationError("Invalid base URL")
            raise e
        except Exception as e:
            raise ToolProviderCredentialValidationError(str(e))

    def validate_url(self, base_url):
        parsed_url = urlparse(base_url)
        return parsed_url.scheme in ['http', 'https'] and parsed_url.netloc
