<div align="center">

![GitHub release (latest by date)](https://img.shields.io/github/v/release/TheSkyC/LexiSync?style=flat-square)
![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)
![Python Version](https://img.shields.io/badge/Python-3.8%2B-blue?style=flat-square&logo=python)
</div>
  <p align="center"><a href="../README.md">中文</a> | English | <a href="./README.ja.md">日本語</a><br></p>

# LexiSync
**LexiSync** is a powerful desktop application designed to provide a comprehensive and efficient localization solution. From smart text extraction to AI-assisted translation and data-driven quality assurance, it significantly simplifies the management process of multilingual content.

This tool is fully compatible with industry-standard PO/POT files and also supports *Overwatch* Workshop code translation, making it a universal localization editing and management platform.

---

## 📥 Download
You can download the latest version from the **[GitHub Releases](https://github.com/TheSkyC/LexiSync/releases/latest)** page.

[![GitHub release (latest by date)](https://img.shields.io/github/v/release/TheSkyC/LexiSync?style=for-the-badge)](https://github.com/TheSkyC/LexiSync/releases/latest)


## 🚀 Core Features

### 📂 Project Management System
*   **Multi-file Support**: Manage multiple source files simultaneously within a single project.
*   **Project Structure**: Clear architecture for easy version control.
*   **Smart Re-scan**: Intelligently detects changes when source files are updated.
*   **One-click Build**: Fully automated build process that generates translated files for all target languages with a single click.

### 🖥️ Modern Interactive Interface
*   **Dual-Track MarkerBar**:
    *   **Point Markers**: Intuitively displays errors, warnings, and search results on the left side of the scrollbar.
    *   **Range Markers**: Displays current selection ranges and Git change status (added/modified) on the right side.
    *   **Interaction**: Supports hover tooltips for details and click-to-jump navigation.
*   **Context Preview**: Real-time display of context lines from code or PO files during translation, supporting keyword highlighting and precise positioning.

### 🤖 AI & Automation
*   **Smart String Extraction**: Automatically extracts translatable strings from code files using customizable regular expressions.
*   **AI-Assisted Translation**: Integrated with OpenAI API, supporting single or batch translation. Smartly identifies placeholders and can reference project glossaries and context information.
*   **Automated QA**:
    *   **Real-time Validation**: Instantly detects errors such as missing placeholders, inconsistent punctuation, and leading/trailing spaces during input.
    *   **Expansion Ratio Check**: Detects translation length anomalies based on big data models.

### 🛠️ Highly Customizable
Application configuration is stored in the `config.json` file in the root directory. It can be configured via the application UI:
*   **AI Settings**: `Tools(T) > AI Settings...`
*   **Extraction Rules**: `Tools(T) > Extraction Rule Manager...`
*   **Keybindings**: `Settings(S) > Keybinding Settings...`
*   **Fonts**: `Settings(S) > Font Settings...`


## 📸 Screenshots
*Main Interface*

<img width="800" height="600" alt="image" src="https://github.com/user-attachments/assets/3d45751c-1b48-47a9-9a9c-df3f62a6d912" />
<img width="800" height="600" alt="image" src="https://github.com/user-attachments/assets/8fc10914-0417-4165-b2ae-874fa433963d" />


<details>
<summary><b>► Click to view more screenshots</b></summary>

*Custom AI Configuration*

<img width="800" height="700" alt="image" src="https://github.com/user-attachments/assets/71384ff5-cd27-415f-b549-31ffec65c5cc" />

*Project Statistics*

<img width="800" height="600" alt="image" src="https://github.com/user-attachments/assets/4d6cf519-d5c9-4269-ba40-bd567854e0b1" />

*Language Pair Settings*

<img width="550" height="680" alt="image" src="https://github.com/user-attachments/assets/4a353f79-7b3f-445f-9c94-b4027f6fea73" />

*Plugin Settings*

<img width="800" height="600" alt="image" src="https://github.com/user-attachments/assets/9ac8965e-c980-43e1-9961-99c4033affcf" />
</details>


## 🛠️ Development Setup

### Prerequisites
*   Python 3.8 or higher
*   Git (Optional, for cloning the repository)

### Steps
1.  **Clone Repository (or download ZIP)**
    ```bash
    git clone https://github.com/TheSkyC/LexiSync.git
    cd LexiSync
    ```

2.  **Create and Activate Virtual Environment (Recommended)**
    ```bash
    python -m venv venv
    # Windows
    .\venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```

3.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run**
    ```bash
    python main.py
    ```

## 🚀 Quick Start

LexiSync offers two flexible working modes to suit different usage scenarios:

### 1. ⚡ Quick Edit Mode
*Suitable for quick modifications of single files, temporary viewing, or lightweight tasks.*

1.  **Open**: Drag a single source file directly into the main interface, or click `File > Open File` in the menu bar.
2.  **Translate**: Use AI assistance and glossary hints to translate as usual.
3.  **Save**: Press `Ctrl+S` to save changes directly.

### 2. 📂 Project Mode
*Suitable for large projects involving multiple files and languages that require long-term maintenance and version control.*

1.  **Create Project**: Click `New Project` (Ctrl+Shift+N), and batch drag in your source files. You can also drag in `.tbx` or `.xlsx` files directly to bind project-specific glossaries and translation memories.
2.  **Manage & Translate**: Double-click in the file explorer on the left to seamlessly switch between different source files. Use the **MarkerBar** on the right to quickly locate errors, warnings, and the current editing position.
3.  **Build & Deliver**: After verification, click `File > Build Project` (Ctrl+B). The program will automatically generate the final translated files for all target languages in the background and output them neatly to the `target/` directory.

## 🌐 Supported Languages
This tool supports translation for any language, and provides localized UI for the following languages:
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
Contributions of any kind are welcome! If you have any questions, feature suggestions, or find a bug, please feel free to submit via GitHub Issues.

## 📄 License
This project is open-sourced under the [Apache 2.0](LICENSE) license, allowing free use, modification, and distribution, provided that the copyright notice is retained.

## 📞 Contact
- Author: TheSkyC
- Email: 0x4fe6@gmail.com
