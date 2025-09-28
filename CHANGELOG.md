# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2024-09-28

### Added
- Initial release of Watercrawl Dify datasource plugin
- Web crawling datasource with recursive page discovery
- Configurable crawl depth and page limits
- URL pattern filtering (include/exclude patterns)
- Fast crawling mode with rendering bypass
- Main content extraction with navigation filtering
- Support for both cloud and self-hosted Watercrawl instances
- Structured output with title, description, and markdown content
- Proxy server support
- Comprehensive documentation and troubleshooting guide

### Configuration
- `url` - Starting URL for crawl (required)
- `max_depth` - Maximum crawl depth (default: 1)
- `limit` - Maximum pages to crawl (default: 1) 
- `ignore_rendering` - Skip page rendering for speed (default: false)
- `include_paths` - URL patterns to include
- `exclude_paths` - URL patterns to exclude
- `only_main_content` - Extract main content only (default: false)
- `proxy_server_slug` - Optional proxy configuration
