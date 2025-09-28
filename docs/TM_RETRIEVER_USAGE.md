# TM Repository Cataloging System - Usage Guide

## Overview

The TM Repository Cataloging System (`TM_retriever.py`) is a comprehensive tool designed to catalog all Tibetan-English text repositories within the MonlamAI GitHub organization whose names start with "TM". This system provides detailed metadata, file statistics, and extracted titles to help track translation sources and estimate translation pairs.

## Features

- **Automatic Repository Discovery**: Finds all repositories starting with "TM" in the MonlamAI organization
- **Intelligent File Identification**: Locates Tibetan (bo) and English (en) .txt files using smart matching
- **Line Counting**: Counts both total lines and non-empty lines for each file
- **Title Extraction**: Extracts titles using language-specific rules and Tibetan markers
- **CSV Catalog Generation**: Creates a structured CSV with comprehensive metadata
- **Error Handling**: Robust error handling for various edge cases
- **Progress Logging**: Detailed logging and progress reporting

## Prerequisites

1. **Python Environment**: Python 3.7+ with required packages (see `requirementx.txt`)
2. **GitHub Access**: Personal Access Token with appropriate permissions
3. **MonlamAI Organization Access**: Access to the MonlamAI GitHub organization

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirementx.txt
```

### 2. Configure GitHub Authentication

1. Create a GitHub Personal Access Token:
   - Go to GitHub Settings → Developer settings → Personal access tokens → Fine-grained tokens
   - Click "Generate new token"
   - Set expiration (recommended: 90 days)
   - Select "MonlamAI" as the resource owner
   - Grant permissions:
     - Repository access: All repositories (or select specific TM* repos)
     - Repository permissions: Contents (Read), Metadata (Read)

2. Create a `.env` file in the project root:
   ```bash
   cp .env.example .env
   ```

3. Edit `.env` and add your token:
   ```
   GITHUB_TOKEN=your_actual_github_token_here
   ```

### 3. Run the Cataloging System

```bash
cd src/
python TM_retriever.py
```

## Output

### CSV Catalog Structure

The system generates `tm_repos_catalog.csv` with the following columns:

| Column | Description |
|--------|-------------|
| `repo_name` | GitHub repository name (e.g., TMtoh1024_84000) |
| `repo_url` | HTTPS link to the repository |
| `bo_file_path` | Path to Tibetan file (empty if missing) |
| `bo_lines_nonempty` | Non-empty line count in Tibetan file |
| `bo_lines_total` | Total line count in Tibetan file |
| `bo_title` | Extracted Tibetan title |
| `en_file_path` | Path to English file (empty if missing) |
| `en_lines_nonempty` | Non-empty line count in English file |
| `en_lines_total` | Total line count in English file |
| `en_title` | Extracted English title |
| `notes` | Issues/anomalies (e.g., missing files, errors) |

### Log Files

- `tm_retriever.log`: Detailed execution log with progress and error information
- Console output: Real-time progress and summary statistics

## File Selection Logic

### Language Detection
- **Tibetan files**: Filenames containing "bo" (case-insensitive)
- **English files**: Filenames containing "en" (case-insensitive)

### Best File Selection
When multiple candidates exist, the system selects files based on:
1. **Path depth**: Prefers files closer to repository root
2. **Filename length**: Prefers shorter filenames (tie-breaker)

### Title Extraction Rules

#### English Titles
- Takes the first non-empty line from the file

#### Tibetan Titles
- Searches the first ~10 non-empty lines for markers:
  - `བོད་སྐད་དུ` (Primary marker)
  - `མདོ།` (Sutra marker)
  - `སྔགས།` (Mantra marker)
  - `གཟུངས།` (Dharani marker)
- Falls back to the first non-empty line if no marker found

## Error Handling

The system handles various edge cases:

- **Missing files**: Records repositories with no .txt files
- **Encoding issues**: Tries UTF-8, UTF-16, and Latin-1 encodings
- **API rate limits**: Includes respectful delays between requests
- **Access errors**: Logs and continues processing other repositories
- **Multiple candidates**: Records alternatives in notes field

## Customization

### Modifying Tibetan Markers

To add or modify Tibetan title markers, edit the `tibetan_markers` list in the `TMRepositoryCatalogger` class:

```python
self.tibetan_markers = [
    "བོད་སྐད་དུ",  # Primary marker
    "མདོ།",        # Sutra marker
    "སྔགས།",      # Mantra marker  
    "གཟུངས།",     # Dharani marker
    "your_custom_marker"  # Add custom markers here
]
```

### Changing Output Location

Modify the output path in the `main()` function:

```python
output_path = "your/custom/path/tm_repos_catalog.csv"
catalogger.generate_csv_catalog(output_path)
```

### Organization Name

To catalog a different organization, modify the initialization:

```python
catalogger = TMRepositoryCatalogger(github_token, org_name="YourOrgName")
```

## Troubleshooting

### Common Issues

1. **Authentication Error**
   - Verify your GitHub token is correct
   - Ensure token has proper permissions
   - Check if token has expired

2. **No Repositories Found**
   - Verify access to MonlamAI organization
   - Check if TM* repositories exist
   - Ensure token has organization access

3. **File Access Errors**
   - Some repositories might be private
   - Token might lack sufficient permissions
   - Repository might be empty or archived

4. **Encoding Errors**
   - System tries multiple encodings automatically
   - Check log files for specific encoding issues
   - Some files might have unusual encodings

### Performance Considerations

- **Rate Limiting**: System includes 1-second delays between API calls
- **Large Repositories**: Deep directory structures may take longer to process
- **Network Issues**: Temporary network problems are logged but don't stop processing

## Summary Statistics

After completion, the system provides:
- Total TM repositories found
- Count of repositories with both bo and en files
- Count of repositories with only bo or en files
- Count of repositories with no .txt files
- Average line counts for successful extractions

## Example Output

```
2025-09-23 11:43:47 - INFO - Authenticated as: your_username
2025-09-23 11:43:48 - INFO - Successfully connected to organization: MonlamAI
2025-09-23 11:43:49 - INFO - Discovering TM* repositories...
2025-09-23 11:43:50 - INFO - Found TM repository: TMtoh1024_84000
2025-09-23 11:43:51 - INFO - Total TM repositories found: 15
2025-09-23 11:43:52 - INFO - Processing repository 1/15: TMtoh1024_84000
...
2025-09-23 11:45:30 - INFO - === CATALOG SUMMARY ===
2025-09-23 11:45:30 - INFO - Total TM repositories found: 15
2025-09-23 11:45:30 - INFO - Repositories with both bo and en files: 12
2025-09-23 11:45:30 - INFO - Repositories with only bo files: 2
2025-09-23 11:45:30 - INFO - Repositories with only en files: 1
2025-09-23 11:45:30 - INFO - Repositories with no txt files: 0
```

## Support

For issues or questions:
1. Check the log files for detailed error information
2. Verify your GitHub token and permissions
3. Ensure all dependencies are installed correctly
4. Review this documentation for configuration options
