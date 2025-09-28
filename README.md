# Watercrawl Datasource Plugin for Dify

[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](https://github.com/watercrawl/watercrawl-dify-datasource)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](#)

A powerful Dify datasource plugin that integrates with [Watercrawl](https://watercrawl.dev) to recursively crawl websites and extract clean, LLM-ready content for AI applications.

## 🚀 Quick Start

1. **Get API Key**: Sign up at [Watercrawl](https://app.watercrawl.dev) and get your API key
2. **Install Plugin**: Add the Watercrawl datasource in your Dify workspace
3. **Configure**: Enter your API key and start crawling websites
4. **Extract**: Get clean, structured content ready for your AI models

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🕷️ **Recursive Crawling** | Automatically discover and crawl linked pages |
| ⚡ **Fast Mode** | Skip rendering for 3x faster crawling |
| 📏 **Depth Control** | Limit crawl depth to control scope |
| 🎯 **Smart Extraction** | Extract main content, skip navigation/ads |
| 🔍 **URL Filtering** | Include/exclude specific URL patterns |
| 📊 **Progress Tracking** | Real-time crawl status monitoring |
| 📝 **Clean Output** | Markdown-formatted, LLM-optimized content |
| 🏠 **Self-Hosted** | Use cloud service or your own instance |

## Setup

### Prerequisites

Before using this plugin, you need:
1. A Watercrawl API key (for cloud service) or self-hosted Watercrawl instance
2. Target URLs ready for crawling
3. Understanding of your crawling requirements (depth, limits, patterns)

### ☁️ Cloud Setup (Recommended)

```bash
# 1. Get your API key from Watercrawl dashboard
https://app.watercrawl.dev/dashboard/api-keys

# 2. Configure in Dify
Base URL: https://api.watercrawl.dev  # (or leave empty)
API Key: wc_your_api_key_here
```

### 🏠 Self-Hosted Setup

```bash
# 1. Deploy your Watercrawl instance
# Follow: https://docs.watercrawl.dev/self-hosted/overview

# 2. Configure in Dify  
Base URL: https://your-watercrawl-instance.com
API Key: any-value  # (required but can be arbitrary)
```

## 📖 Usage Examples

### 📄 Single Page Extraction
Extract content from one specific page:
```yaml
Start URL: https://example.com/article
Maximum crawl depth: 1
Maximum pages to crawl: 1
Only main content: true
```

### 🌐 Full Website Crawl
Crawl an entire website systematically:
```yaml
Start URL: https://example.com
Maximum crawl depth: 2
Maximum pages to crawl: 50
URL patterns to include: # (optional)
URL patterns to exclude: admin/*, login/*
```

### 🎯 Targeted Section Crawl
Focus on specific website sections:
```yaml
Start URL: https://docs.example.com
Maximum crawl depth: 3
Maximum pages to crawl: 100
URL patterns to include: api/*, guides/*, tutorials/*
URL patterns to exclude: archive/*, changelog/*
```

## ⚙️ Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| **Start URL** | `string` | *required* | Base URL to begin crawling |
| **Ignore rendering** | `boolean` | `false` | Skip page rendering for faster crawling |
| **URL patterns to exclude** | `string` | - | Comma-separated exclude patterns: `blog/*, about/*` |
| **URL patterns to include** | `string` | - | Comma-separated include patterns: `docs/*, api/*` |
| **Maximum crawl depth** | `number` | `1` | How deep to crawl (1 = start URL only) |
| **Maximum pages to crawl** | `number` | `1` | Total page limit for the crawl job |
| **Only main content** | `boolean` | `false` | Extract main content, skip nav/footer |
| **Proxy Server Slug** | `string` | - | Proxy server identifier (optional) |

### 🎯 Understanding Crawl Depth

```
Depth 1: [Start URL] → Direct links
Depth 2: [Start URL] → Direct links → Links from those pages
Depth 3: [Start URL] → Direct links → 2nd level → 3rd level pages
```

### 🔍 URL Pattern Examples

**Include Only Specific Sections:**
```
blog/*, docs/api/*, products/*/specs
```

**Exclude Unwanted Areas:**
```
admin/*, login/*, tag/*, category/*
```

## 📤 Output Format

Each crawled page returns structured data:

```json
{
  "source_url": "https://example.com/page",
  "title": "Page Title", 
  "description": "Meta description",
  "content": "# Clean Markdown Content\n\nParagraph text..."
}
```

## 🔄 How It Works

1. **Job Creation** → Submit crawl request to Watercrawl API
2. **Processing** → Watercrawl crawls pages based on your parameters  
3. **Monitoring** → Plugin polls job status every 5 seconds
4. **Extraction** → Content is cleaned and formatted as Markdown
5. **Delivery** → Structured results returned to Dify

## 🎯 Common Use Cases

<details>
<summary><strong>📚 Documentation Indexing</strong></summary>

Perfect for creating AI-powered knowledge bases:
```yaml
Start URL: https://docs.example.com
Maximum crawl depth: 3
Maximum pages to crawl: 200
URL patterns to include: api/*, guides/*, tutorials/*
URL patterns to exclude: changelog/*, archive/*
Only main content: true
```
</details>

<details>
<summary><strong>📝 Content Analysis</strong></summary>

Extract blog posts and articles for analysis:
```yaml
Start URL: https://blog.example.com
Maximum crawl depth: 2
Maximum pages to crawl: 100
URL patterns to include: posts/*, articles/*
URL patterns to exclude: tag/*, author/*, comments/*
Only main content: true
```
</details>

<details>
<summary><strong>🛍️ E-commerce Data</strong></summary>

Gather product information systematically:
```yaml
Start URL: https://shop.example.com/products
Maximum crawl depth: 2
Maximum pages to crawl: 50
URL patterns to include: products/*
URL patterns to exclude: cart/*, checkout/*, account/*
Only main content: true
```
</details>

<details>
<summary><strong>🔍 Competitor Research</strong></summary>

Monitor competitor websites for changes:
```yaml
Start URL: https://competitor.com
Maximum crawl depth: 2
URL patterns to include: products/*, pricing/*, features/*
URL patterns to exclude: blog/*, news/*, support/*
```
</details>

## 💡 Best Practices

- 🧪 **Start Small**: Test with low limits first (`depth: 1`, `limit: 5`)
- 🎯 **Use Filters**: Focus crawling with include/exclude patterns  
- 🤖 **Respect Robots**: Check `robots.txt` before large crawls
- ⚡ **Fast Mode**: Use `ignore_rendering: true` for speed
- 📄 **Main Content**: Enable for cleaner, AI-ready content
- 📊 **Monitor**: Watch crawl progress for large jobs
- 🔄 **Iterate**: Refine patterns based on results

## ⚡ Performance Notes

| Scenario | Typical Time | Recommendation |
|----------|--------------|----------------|
| Single page | < 5 seconds | Use for quick extractions |
| Small site (< 20 pages) | 30-60 seconds | Good for testing patterns |
| Medium site (50-100 pages) | 2-5 minutes | Monitor progress |
| Large site (> 200 pages) | 5-15 minutes | Use during off-hours |

> 💡 **Tip**: Deep crawling (depth > 3) can exponentially increase page count. Use cautiously!

## 🔧 Troubleshooting

<details>
<summary><strong>❌ Authentication Errors</strong></summary>

**"API key is required" error:**
- ✅ Verify API key in Dify plugin settings
- ✅ Check Base URL is correct (`https://api.watercrawl.dev`)
- ✅ Ensure API key starts with `wc-`

</details>

<details>
<summary><strong>🚫 Crawl Failures</strong></summary>

**"Failed to crawl" error:**
- ✅ Test URL accessibility in browser
- ✅ Check if site blocks bots (robots.txt)
- ✅ Verify API key is valid and has credits
- ✅ Try with `ignore_rendering: true`

</details>

<details>
<summary><strong>📉 Incomplete Results</strong></summary>

**Missing expected pages:**
- ✅ Verify URL patterns with [pattern tester](https://globster.xyz/)
- ✅ Check crawl depth covers target pages
- ✅ Increase page limit if needed
- ✅ Review site's internal linking structure

</details>

<details>
<summary><strong>🐌 Performance Issues</strong></summary>

**Crawling too slow:**
- ✅ Enable `ignore_rendering` for 3x speed boost
- ✅ Use more specific URL patterns
- ✅ Reduce crawl depth and page limits
- ✅ Check your internet connection

</details>

## 📊 Rate Limits & Usage

### ☁️ Watercrawl Cloud
- **Free Plan**: 1000 pages/month
- **Startup Plan**: 10,000 pages/month
- **Pro Plan**: 30,000 pages/month
- **Enterprise**: Custom limits
- Check [pricing](https://watercrawl.dev/pricing) for more details
- Monitor usage: [Dashboard](https://app.watercrawl.dev/dashboard)

### 🏠 Self-Hosted
- No external rate limits
- Performance depends on your server resources

## 🔒 Security & Privacy

- 🔐 **Secure**: All API calls use HTTPS encryption
- 🔑 **API Keys**: Store securely, never in client-side code
- 🏠 **Self-Hosted**: Full data control for sensitive content
- 📋 **Review**: Always check crawled content before use

## 📞 Support & Resources

### 🆘 Get Help
- 💬 **Plugin Issues**: [support@watercrawl.dev](mailto:support@watercrawl.dev)
- 📖 **Documentation**: [docs.watercrawl.dev](https://docs.watercrawl.dev)
- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/watercrawl/watercrawl)

### 📚 Learn More
- [📖 API Reference](https://docs.watercrawl.dev/api/documentation/)
- [🏠 Self-Hosting Guide](https://docs.watercrawl.dev/self-hosted/overview)  
- [🚀 Watercrawl Website](https://watercrawl.dev)

---

<div align="center">

**Made with ❤️ by the Watercrawl Team**

[Website](https://watercrawl.dev) • [Documentation](https://docs.watercrawl.dev) • [Dashboard](https://app.watercrawl.dev)

</div>
