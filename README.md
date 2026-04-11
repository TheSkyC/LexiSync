<div align="center">

![LexiSync Logo](https://img.shields.io/badge/LexiSync-409EFF?style=for-the-badge&logo=sync)

![GitHub release (latest by date)](https://img.shields.io/github/v/release/TheSkyC/LexiSync?style=flat-square)
![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)
![Python Version](https://img.shields.io/badge/Python-3.12%2B-blue?style=flat-square&logo=python)
![Vue Version](https://img.shields.io/badge/Vue.js-3.x-4FC08D?style=flat-square&logo=vuedotjs)
</div>
<p align="center">English | <a href="./docs/README.zh.md">中文</a> | <a href="./docs/README.ja.md">日本語</a><br></p>

# LexiSync
**LexiSync** is a next-generation localization collaboration platform designed for developers, translators, and teams. It seamlessly combines powerful desktop performance with real-time Web cloud collaboration, providing a complete solution from text extraction, AI-assisted translation, and quality assurance to multi-device synchronization.

Whether you are a solo developer quickly handling strings in code or a distributed team collaborating on complex multi-language projects, LexiSync significantly streamlines your workflow.

---

## 📥 Download
You can download the latest versions for Windows, macOS, and Linux from the **[GitHub Releases](https://github.com/TheSkyC/LexiSync/releases/latest)** page.

[![GitHub release (latest by date)](https://img.shields.io/github/v/release/TheSkyC/LexiSync?style=for-the-badge)](https://github.com/TheSkyC/LexiSync/releases/latest)

## 🚀 Core Features

### ☁️ Cloud Collaboration
*   **One-Click Hosting**: Turn your local project into a server with one click. Team members can join directly via a browser (Web UI) without installing any clients.
*   **Real-Time Sync**: Any modifications to translations, statuses (reviewed/fuzzy), and comments are broadcast to all online members in milliseconds. Supports collaborative undo/redo on the Web.
*   **Collaborative Awareness & Anti-Conflict**: See which entries other members are editing in real-time (cursor locking). Built-in Myers diff algorithm elegantly resolves concurrent editing conflicts.
*   **Tunneling & Security**: Natively integrates Cloudflare Tunnel to generate secure public access links without a public IP. Built-in Role-Based Access Control (RBAC), granular scope restrictions, IP banning, and persistent audit logs.

### 📂 Comprehensive Format Support (25+ Formats)
*   **Massive Format Compatibility**: Natively supports over 25 industry standards, mainstream frameworks, multimedia, and office document localization files:
    *   **Industry Standards & Desktop UI**: `PO/POT`, `XLIFF`, `Qt TS`
    *   **Mobile & Cross-Platform**: `Android Strings (XML)`, `iOS/macOS (.strings, .stringsdict)`, `Xcode String Catalog (.xcstrings)`, `Flutter ARB`
    *   **Data Serialization & Configs**: `JSON`, `i18next JSON`, `YAML`, `TOML`, `INI`
    *   **Desktop & Backend**: `Java .properties`, `.NET RESX`, `PHP Array`, `Windows RC`
    *   **Tables & Batch Processing**: `CSV`, `Excel (.xlsx)`
    *   **Multimedia & Subtitles**: `SRT`, `VTT`
    *   **Web & Rich Office Documents**: `HTML`, `Markdown/MDX`, `Word (.docx)`, `PowerPoint (.pptx)`
    *   **Custom & Special Formats**: `Mozilla Fluent (.ftl)`, `OwCode(.ow)`
*   **Native Pluralization**: Supports plural rules across languages (Zero/One/Two/Few/Many/Other). AI translation and validation engines are fully adapted to plural contexts.

### 🤖 AI-Driven Smart Workflow
*   **Smart Batch Translation**: Deeply analyzes all text before translation, automatically generating a **style guide**, extracting **key terminology**, and combining **Translation Memory (TM)** and **Semantic Retrieval (RAG)** to provide rich context for AI, drastically improving translation quality and consistency.
*   **Interactive Review Mode**: A brand-new semi-automated workflow. AI pre-translates in the background, and users simply confirm, correct, or skip entries one by one in the UI, balancing efficiency with manual control.
*   **Automated QA**: Real-time detection of missing placeholders, inconsistent punctuation, leading/trailing spaces, etc., during input; supports one-click "Auto Fix" or "AI Fix".

### 🖥️ Modern Interactive Interface
*   **Desktop**: Dual-track marker bar (intuitively displays errors, warnings, search results), real-time context preview, interactive history panel.
*   **Web**: Responsive interface built with Vue 3, supporting dark mode and a built-in real-time chat drawer.

## 📸 Screenshots

*Desktop Main Interface*

<img width="800" alt="Desktop UI" src="docs/assets/ui-desktop.png" />

*Web Real-Time Collaboration*

<img width="800" alt="Web UI" src="docs/assets/ui-web.png" />

<details>
<summary><b>► Click to view more screenshots</b></summary>

*Welcome Screen & Formats*

<img width="800" alt="Welcome Screen & Formats" src="docs/assets/ui-welcome.png" />

*Smart Translation*

<img width="800" alt="Smart Translation" src="docs/assets/feature-smart-translation.png" />

*AI Models Management*

<img width="800" alt="AI Models Management" src="docs/assets/feature-ai-models.png" />

*Plugins Management*

<img width="800" alt="Plugins Management" src="docs/assets/feature-plugins.png" />

</details>

## 🛠️ Development Setup

### Prerequisites
*   Python 3.12 or higher
*   Node.js 20.x or higher (for building the Web frontend)
*   Git (optional, for cloning the repository)

### Steps
1.  **Clone the repository (or download ZIP)**
    ```bash
    git clone https://github.com/TheSkyC/LexiSync.git
    cd LexiSync
    ```

2.  **Create and activate a virtual environment (Recommended)**
    ```bash
    python -m venv venv
    # Windows
    .\venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```

3.  **Install Python dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Build the Web frontend**
    ```bash
    cd web_src
    npm ci
    npm run build
    cd ..
    ```

5.  **Run the application**
    ```bash
    python src/lexisync/main.py
    ```

## 🚀 Quick Start

LexiSync offers three flexible working modes to suit different scenarios:

### 1. ⚡ Quick Edit Mode (Single File)
*Ideal for quick modifications, temporary viewing, or lightweight tasks.*
*   Drag and drop a single file (e.g., `.po`, `.json`, `.strings`) directly into the main interface.
*   Translate using AI assistance and terminology hints as usual.
*   Press `Ctrl+S` to save modifications directly.

### 2. 📂 Project Mode (Local Multi-file)
*Ideal for large projects requiring long-term maintenance and version control across multiple files and languages.*
*   Click `New Project` (Ctrl+Shift+N) and drag in your source files in bulk.
*   Double-click in the left file browser to seamlessly switch between different source files.
*   Once confirmed, click `File > Build Project` (Ctrl+B), and the program will automatically generate the final translated files for all target languages.

### 3. ☁️ Cloud Collaboration Mode (Team Multi-client)
*Ideal for team projects requiring simultaneous translation and review by multiple people.*
*   In Quick/Project mode, open the **"Cloud Collaboration"** panel at the bottom.
*   Click **"Start Cloud Service"**. If external access is needed, check "Enable Public URL (Tunneling)" in the settings.
*   Generate exclusive access Tokens for team members in "Manage Users & Permissions".
*   Members can join the real-time collaboration by visiting the generated link via their browser.

## 🌐 Supported UI Languages
This tool supports translating into any language, and provides localized UI interfaces for the following languages:
*   **English** (`en_US`)
*   **简体中文** (`zh_CN`)
*   **日本語** (`ja_JP`)
*   **한국어** (`ko_KR`)
*   **Français** (`fr_FR`)
*   **Deutsch** (`de_DE`)
*   **Русский** (`ru_RU`)
*   **Español (España)** (`es_ES`)
*   **Italiano** (`it_IT`)

## 🤝 Contributing
Contributions of any kind are welcome! If you have any questions, feature suggestions, or find a bug, please feel free to submit them via GitHub Issues.

## 📄 License
This project is open-sourced under the [Apache 2.0](LICENSE) license, allowing free use, modification, and distribution, provided the copyright notice is retained.

## 📞 Contact
- Author: TheSkyC
- Email: 0x4fe6@gmail.com