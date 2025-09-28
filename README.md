# MT-Catalog: MonlamAI Translation Memory Cataloging System

<h1 align="center">
  <br>
  <a href="https://openpecha.org"><img src="https://avatars.githubusercontent.com/u/82142807?s=400&u=19e108a15566f3a1449bafb03b8dd706a72aebcd&v=4" alt="OpenPecha" width="150"></a>
  <br>
</h1>

## TM Repository Cataloging System
A comprehensive tool for cataloging Tibetan-English translation memory repositories within the MonlamAI GitHub organization. This system automatically discovers, analyzes, and catalogs all repositories starting with "TM" to provide detailed metadata, file statistics, and extracted titles.

## Owner(s)

- MonlamAI Team
- [@ngawangtrinley](https://github.com/ngawangtrinley)
- [@mikkokotila](https://github.com/mikkokotila)
- [@evanyerburgh](https://github.com/evanyerburgh)


## Table of contents
<p align="center">
  <a href="#project-description">Project description</a> •
  <a href="#who-this-project-is-for">Who this project is for</a> •
  <a href="#project-dependencies">Project dependencies</a> •
  <a href="#instructions-for-use">Instructions for use</a> •
  <a href="#contributing-guidelines">Contributing guidelines</a> •
  <a href="#additional-documentation">Additional documentation</a> •
  <a href="#how-to-get-help">How to get help</a> •
  <a href="#terms-of-use">Terms of use</a>
</p>
<hr>

## Project description

The MT-Catalog system helps you **automatically catalog and analyze** all Tibetan-English translation memory repositories within the MonlamAI GitHub organization. 

With MT-Catalog you can:
- **Discover** all repositories starting with "TM" in the MonlamAI organization
- **Identify** Tibetan (bo) and English (en) text files using intelligent matching
- **Extract** titles using language-specific rules and Tibetan markers
- **Count** lines and analyze file statistics
- **Generate** comprehensive CSV catalogs with detailed metadata
- **Track** translation sources and estimate translation pairs


## Who this project is for
This project is intended for:
- **MonlamAI team members** who need to track and catalog translation memory repositories
- **Researchers** studying Tibetan-English parallel text corpora
- **Data scientists** working with translation pair datasets
- **Project managers** tracking translation sources and preventing duplicate work


## Project dependencies
Before using MT-Catalog, ensure you have:
* **Python 3.7+** with pip package manager
* **GitHub Personal Access Token** with MonlamAI organization access
* **Repository permissions** to read MonlamAI TM* repositories
* **Required Python packages** (see `requirementx.txt`)


## Instructions for use
Get started with MT-Catalog by **cloning the repository** and setting up your GitHub authentication.

### Install MT-Catalog
1. **Clone the repository**
   ```bash
   git clone https://github.com/MonlamAI/MT-Catalog.git
   cd MT-Catalog
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirementx.txt
   ```

### Configure MT-Catalog
1. **Set up GitHub authentication**
   ```bash
   cp .env.example .env
   ```
   
2. **Add your GitHub token to `.env`**
   ```
   GITHUB_TOKEN=your_github_personal_access_token_here
   ```
   
   See [GitHub Token Setup Guide](docs/TM_RETRIEVER_USAGE.md#setup-instructions) for detailed instructions.

### Run MT-Catalog
1. **Navigate to the source directory**
   ```bash
   cd src/
   ```
   
2. **Execute the cataloging system**
   ```bash
   python TM_retriever.py
   ```
   
3. **Check the output**
   - CSV catalog: `../output_csv/tm_repos_catalog.csv`
   - Log file: `tm_retriever.log`


### Troubleshoot MT-Catalog
1. **Check log files** for detailed error information (`tm_retriever.log`)
2. **Verify GitHub token** permissions and expiration
3. **Ensure network connectivity** to GitHub API

<table>
  <tr>
   <td>
    Issue
   </td>
   <td>
    Solution
   </td>
  </tr>
  <tr>
   <td>
    Authentication Error
   </td>
   <td>
    Verify GitHub token is correct and has proper permissions
   </td>
  </tr>
  <tr>
   <td>
    No Repositories Found
   </td>
   <td>
    Check access to MonlamAI organization and TM* repositories exist
   </td>
  </tr>
  <tr>
   <td>
    File Access Errors
   </td>
   <td>
    Ensure token has repository read permissions for private repos
   </td>
  </tr>
</table>

Other troubleshooting supports:
* [Detailed Usage Guide](docs/TM_RETRIEVER_USAGE.md)
* [GitHub Token Setup Instructions](docs/TM_RETRIEVER_USAGE.md#setup-instructions)
* [Error Handling Documentation](docs/TM_RETRIEVER_USAGE.md#troubleshooting)


## Contributing guidelines
If you'd like to help out, check out our [contributing guidelines](/CONTRIBUTING.md).


## Additional documentation

For comprehensive documentation and advanced usage:

* [**TM_retriever Usage Guide**](docs/TM_RETRIEVER_USAGE.md) - Complete setup and usage instructions
* [**GitHub Token Setup**](docs/TM_RETRIEVER_USAGE.md#setup-instructions) - Step-by-step authentication guide
* [**CSV Output Format**](docs/TM_RETRIEVER_USAGE.md#csv-catalog-structure) - Detailed column descriptions
* [**Customization Options**](docs/TM_RETRIEVER_USAGE.md#customization) - How to modify the system for your needs


## How to get help
* File an issue.
* Email us at openpecha[at]gmail.com.
* Join our [discord](https://discord.com/invite/7GFpPFSTeA).


## Terms of use
MT-Catalog is licensed under the [MIT License](/LICENSE.md).
