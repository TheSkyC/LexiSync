<div align="center">

![GitHub release (latest by date)](https://img.shields.io/github/v/release/TheSkyC/Overwatch-Localizer?style=flat-square)
![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)
![Python Version](https://img.shields.io/badge/Python-3.8%2B-blue?style=flat-square&logo=python)
</div>
  <p align="center">中文 | <a href="./docs/README.en.md">English</a> | <a href="./docs/README.ja.md">日本語</a><br></p>

# Overwatch Localizer

**Overwatch Localizer** 是一款功能强大的桌面应用程序，专为《守望先锋》工坊创作者、模组开发者和专业翻译人员设计。它提供了一套完整、高效的本地化解决方案，从智能提取文本，到辅助翻译，再到无缝集成，极大简化了多语言内容的管理流程。

本工具不仅支持《守望先锋》的自定义代码格式，还兼容行业标准的 PO/POT 文件，使其成为一个通用的本地化编辑和管理平台。

---

## 🚀 主要功能

### 核心翻译功能
*   **直观的翻译界面**：并排显示原文、译文、注释和状态，提供上下文预览。
*   **翻译记忆库 (TM)**：支持导入/导出 Excel 格式的翻译记忆库，自动应用匹配，并提供模糊匹配建议。
*   **标准本地化支持**:
    *   **完整的 PO/POT 工作流**：可直接创建、编辑和管理 PO 文件。
    *   **版本对比与合并**：支持将 PO 文件与新的 POT 模板进行对比，智能合并新旧内容。

### 项目与工作流
*   **双重项目模式**：
    *   **工坊代码模式**：直接从 `.ow` 或 `.txt` 代码文件中提取可翻译字符串，并将翻译结果回写到新代码中。
    *   **PO 文件模式**：提供独立的 PO 文件编辑工作流，无需关联任何代码文件。
*   **项目管理**：支持保存/加载项目文件 (`.owproj`)，完整保留您的工作进度、筛选视图和配置。

### 自动化与智能
*   **智能字符串提取**：自动识别并提取代码文件中的可翻译字符串，支持自定义正则表达式规则，并能智能过滤无需翻译的内容（如纯数字、占位符等）。
*   **集成 AI 翻译**：
    *   通过调用大语言模型（兼容 OpenAI API）实现高质量的机器翻译。
    *   支持批量翻译、上下文引用和项目专属指令，优化翻译的准确性和风格。
*   **质量保证 (QA)**：
    *   **内置验证系统**：自动检测翻译中的常见错误。
    *   **智能验证**：如占位符不匹配、行数不一致、首尾空格/标点不匹配等。

### 高度可定制
*   **自定义提取规则**：通过图形化界面管理字符串提取规则，适应各种代码格式。
*   **自定义 AI 提示词**：精细控制 AI 翻译的行为、语气和专业术语。
*   **自定义快捷键**：根据您的操作习惯，为常用功能设置专属快捷键。
*   **自定义字体**: 在设置中为不同语言（如拉丁、CJK、西里尔）指定显示字体，确保全球化文本的最佳视觉效果。

## 🛠️ 自定义配置
应用程序的配置存储在 `localization_tool_config.json` 文件中。您可以通过应用程序的UI轻松进行配置：

*   **AI 翻译设置**: `工具(T) > AI翻译设置...`
*   **提取规则管理器**: `工具(T) > 提取规则管理器...`
*   **快捷键设置**: `设置(S) > 快捷键设置...`
*   **字体设置**: `设置(S) > 字体设置...`

## 📥 下载
您可以从 **[GitHub Releases](https://github.com/TheSkyC/overwatch-localizer/releases/latest)** 页面下载最新版本。

[![GitHub release (latest by date)](https://img.shields.io/github/v/release/TheSkyC/Overwatch-Localizer?style=for-the-badge)](https://github.com/TheSkyC/overwatch-localizer/releases/latest)

## 📸 截图
*主界面*
![image](https://github.com/user-attachments/assets/4f164e2c-ef08-493a-9555-ca7867614a5a)


<details>
<summary><b>► 点击查看更多截图</b></summary>

*AI翻译、提取规则、快捷键和字体均可自定义。*
![image](https://github.com/user-attachments/assets/5870964c-2667-4b2e-a86a-2d33f1d3e448)
![image](https://github.com/user-attachments/assets/dbb2fd73-9eb0-46e6-81fa-130ac9f68c9c)

</details>


## 🛠️ 开发环境设置

### 前提条件
*   Python 3.8 或更高版本
*   Git (可选，用于克隆仓库)

### 步骤
1.  **克隆仓库 (或下载 ZIP)**
    ```bash
    git clone https://github.com/TheSkyC/Overwatch-Localizer.git
    cd Overwatch-Localizer
    ```

2.  **创建并激活虚拟环境 (推荐)**
    ```bash
    python -m venv venv
    # Windows
    .\venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```

3.  **安装依赖**
    ```bash
    pip install -r requirements.txt
    ```

## 🚀 使用方法
1.  **启动应用程序**
    ```bash
    python main.py
    ```
2.  **基本工作流程**
    *   **工坊代码工作流**:
        1.  打开 `.ow` / `.txt` 代码文件或 `.owproj` 项目文件。
        2.  在右侧编辑框中进行翻译，使用 `Ctrl+Enter` 应用并跳转到下一项。
        3.  点击 `文件(F) > 保存` 来保存 `.owproj` 项目。
        4.  完成后，点击 `文件(F) > 保存翻译到新代码文件` 生成翻译后的代码。

    *   **PO 文件工作流**:
        1.  打开 `.po` 文件或从 `.pot` 模板文件开始。
        2.  进行翻译和审阅。带有 `fuzzy` 标志的条目会自动以淡黄色背景高亮。
        3.  如需更新，点击 `文件(F) > 版本对比/导入新版代码...` 并选择新的 `.pot` 文件进行合并。
        4.  完成后，点击 `文件(F) > 保存` 来保存 `.po` 文件。

3.  **AI 翻译与质量保证**
    *   在 `工具(T) > AI翻译设置...` 中配置 API。
    *   选择条目后，使用右键菜单或快捷键进行 AI 翻译。
    *   留意状态列的 "⚠️" 图标，将鼠标悬停在状态栏上查看详细的警告信息。

## 🌐 支持的语言
本工具支持对任意语言的翻译，并为以下语言的UI提供了本地化界面：
*   **English** (`en_US`)
*   **简体中文** (`zh_CN`)
*   **日本語** (`ja_JP`)
*   **한국어** (`ko_KR`)
*   **le français** (`fr_FR`)
*   **Deutsch** (`de_DE`)
*   **русский язык** (`ru_RU`)
*   **español (España)** (`es_ES`)
*   **italiano** (`it_IT`)

## 🤝 贡献
欢迎任何形式的贡献！如果您有任何问题、功能建议或发现 Bug，请随时通过 GitHub Issues 提交。

## 📄 许可证
本项目基于 [Apache 2.0](LICENSE) 开源，允许自由使用、修改和分发，但需保留版权声明。

## 📞 联系
作者：骰子掷上帝 (TheSkyC)
国服ID：小鸟游六花#56683
亚服ID：小鳥游六花#31665
