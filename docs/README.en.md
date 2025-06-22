<div align="center">

![GitHub release (latest by date)](https://img.shields.io/github/v/release/TheSkyC/Overwatch-Localizer?style=flat-square)
![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)
![Python Version](https://img.shields.io/badge/Python-3.8%2B-blue?style=flat-square&logo=python)
</div>
  <p align="center"><a href="./README.md">中文</a> | English | <a href="./docs/README.ja.md">日本語</a><br></p>

# Overwatch Localizer

**Overwatch Localizer** is a powerful desktop application designed for Overwatch Workshop creators, mod developers, and professional translators. It provides a complete and efficient localization solution, from intelligent text extraction to assisted translation and seamless integration, significantly simplifying the management of multilingual content.

This tool not only supports Overwatch's custom code format but is also compatible with industry-standard PO/POT files, making it a versatile platform for localization editing and management.

---

## 🚀 Key Features

### Core Translation Functionality
*   **Intuitive Translation Interface**: Side-by-side display of original text, translation, comments, and status, with a context preview.
*   **Translation Memory (TM)**: Supports importing/exporting TM in Excel format, with automatic matching and fuzzy match suggestions.
*   **Standard Localization Support**:
    *   **Complete PO/POT Workflow**: Directly create, edit, and manage PO files.
    *   **Version Comparison & Merging**: Compare PO files with new POT templates to intelligently merge new and updated content.

### Project & Workflow Management
*   **Dual Project Modes**:
    *   **Workshop Code Mode**: Directly extract translatable strings from `.ow` or `.txt` code files and write the translations back into a new code file.
    *   **PO File Mode**: Provides a standalone PO file editing workflow, independent of any associated code files.
*   **Project Management**: Save and load project files (`.owproj`) to preserve your work progress, filter views, and configurations.

### Automation & Intelligence
*   **Smart String Extraction**: Automatically identifies and extracts translatable strings from code files, supports custom regex rules, and intelligently filters out non-translatable content (e.g., numbers, placeholders).
*   **Integrated AI Translation**:
    *   Achieve high-quality machine translation by leveraging Large Language Models (compatible with OpenAI API).
    *   Supports batch translation, context referencing, and project-specific instructions to enhance accuracy and style.
*   **Quality Assurance (QA)**:
    *   **Built-in Validation System**: Automatically detects common errors in translations.
    *   **Smart Validation**: Checks for placeholder mismatches, inconsistent line counts, and mismatched leading/trailing spaces or punctuation.

### High Customizability
*   **Custom Extraction Rules**: Manage string extraction rules through a graphical interface to adapt to various code formats.
*   **Custom AI Prompts**: Fine-tune the behavior, tone, and terminology of AI translations.
*   **Custom Hotkeys**: Set personalized shortcuts for frequently used functions to match your workflow.
*   **Custom Fonts**: Specify display fonts for different language scripts (e.g., Latin, CJK, Cyrillic) in the settings for optimal visual presentation of global text.

## 🛠️ Custom Configuration
Application settings are stored in the `localization_tool_config.json` file. You can easily configure them through the application's UI:

*   **AI Translation Settings**: `Tools (T) > AI Settings...`
*   **Extraction Rule Manager**: `Tools (T) > Extraction Rule Manager...`
*   **Hotkey Settings**: `Settings (S) > Keybinding Settings...`
*   **Font Settings**: `Settings (S) > Font Settings...`

## 📥 Download
You can download the latest version from the **[GitHub Releases](https://github.com/TheSkyC/overwatch-localizer/releases/latest)** page.

[![GitHub release (latest by date)](https://img.shields.io/github/v/release/TheSkyC/Overwatch-Localizer?style=for-the-badge)](https://github.com/TheSkyC/overwatch-localizer/releases/latest)

## 📸 Screenshots
*Main Interface*
![image](https://github.com/user-attachments/assets/4f164e2c-ef08-493a-9555-ca7867614a5a)

<details>
<summary><b>► Click to see more screenshots</b></summary>

*AI translation, extraction rules, hotkeys, and fonts are all customizable.*
![image](https://github.com/user-attachments/assets/5870964c-2667-4b2e-a86a-2d33f1d3e448)
![image](https://github.com/user-attachments/assets/dbb2fd73-9eb0-46e6-81fa-130ac9f68c9c)

</details>

## 🛠️ Setup for Development

### Prerequisites
*   Python 3.8 or higher
*   Git (optional, for cloning the repository)

### Steps
1.  **Clone the repository (or download ZIP)**
    ```bash
    git clone https://github.com/TheSkyC/Overwatch-Localizer.git
    cd Overwatch-Localizer
    ```

2.  **Create and activate a virtual environment (recommended)**
    ```bash
    python -m venv venv
    # Windows
    .\venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```

3.  **Install dependencies**
    ```bash
    pip install -r requirements.txt
    ```

## 🚀 How to Use
1.  **Launch the application**
    ```bash
    python main.py
    ```
2.  **Basic Workflows**
    *   **Workshop Code Workflow**:
        1.  Open an `.ow` / `.txt` code file or an `.owproj` project file.
        2.  Enter translations in the editor pane on the right. Use `Ctrl+Enter` to apply and jump to the next item.
        3.  Click `File (F) > Save` to save your `.owproj` project.
        4.  Once finished, click `File (F) > Save Translation to New Code File` to generate the translated code.

    *   **PO File Workflow**:
        1.  Open a `.po` file or start from a `.pot` template.
        2.  Translate and review entries. Items marked as `fuzzy` will be automatically highlighted with a light yellow background.
        3.  To update, click `File (F) > Compare/Import New Version...` and select the new `.pot` file to merge.
        4.  When done, click `File (F) > Save` to save the `.po` file.

3.  **AI Translation & QA**
    *   Configure your API in `Tools (T) > AI Settings...`.
    *   Select entries and use the right-click context menu or hotkeys for AI translation.
    *   Look for the "⚠️" icon in the status column and hover over the status bar to see detailed warning messages.

## 🌐 Supported Languages
This tool supports translation into any language and provides a localized UI for the following languages:
*   **English** (`en_US`)
*   **简体中文** (`zh_CN`)
*   **日本語** (`ja_JP`)
*   **한국어** (`ko_KR`)
*   **le français** (`fr_FR`)
*   **Deutsch** (`de_DE`)
*   **русский язык** (`ru_RU`)
*   **español (España)** (`es_ES`)
*   **italiano** (`it_IT`)

## 🤝 Contributing
Contributions of any kind are welcome! If you have any questions, feature suggestions, or bug reports, please feel free to submit them via GitHub Issues.

## 📄 License
This project is licensed under the [Apache 2.0 License](LICENSE). You are free to use, modify, and distribute it, provided that the copyright notice is retained.

## 📞 Contact
- Author: TheSkyC (骰子掷上帝)
- Email: 0x4fe6@gmail.com
- Battle.net ID (CN): 小鸟游六花#56683
- Battle.net ID (Asia): 小鳥游六花#31665
