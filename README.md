![alt text](https://img.shields.io/github/v/release/TheSkyC/Overwatch-Localizer?style=flat-square)
![alt text](https://img.shields.io/badge/License-Apache%202.0-blue.svg)
![alt text](https://img.shields.io/badge/Python-3.8%2B-blue?style=flat-square&logo=python)

Overwatch Localizer 是一款专为《守望先锋》工坊创作者和翻译人员设计的桌面应用程序。它帮助您从自定义代码中提取可翻译的字符串，进行高效翻译，并支持将翻译后的内容无缝地重新集成回您的代码中。
## 🚀 主要功能

*   **智能字符串提取**：
    *   自动识别并提取代码文件中的可翻译字符串，支持自定义提取规则。
    *   自动识别不需要翻译的内容。
*   **直观的翻译界面**：
    *   并排显示原文、译文、注释和状态。
    *   支持占位符（如 `{0}`）高亮和验证。
    *   上下文预览，帮助理解字符串在代码中的位置。
*   **翻译记忆库**：
    *   支持导入/导出 Excel 格式的翻译记忆库。
    *   自动匹配并应用记忆库。
    *   提供模糊匹配建议。
*   **集成 AI 翻译**：
    *   通过调用大语言模型实现智能翻译（兼容 OpenAI API 的模型）。
    *   可自定义 AI 提示词结构和项目专属翻译指令，以优化翻译质量和风格。
    *   支持上下文引用，帮助 AI 理解语境，优化翻译质量。
    *   支持翻译后的占位符检测。
*   **项目管理**：
    *   保存/加载项目文件（`.owproj`）。
    *   **版本对比与合并**：导入新版代码文件，自动匹配并继承旧版翻译。
*   **标准本地化支持**：
    *   支持导入/导出 PO/POT 文件，与标准翻译工具链集成。
*   **高度可定制**：
    *   自定义字符串提取规则，适应不同代码格式。
    *   自定义 AI 提示词结构，精细控制 AI 翻译行为。
    *   自定义快捷键，提升操作效率。

## 🛠️ 自定义配置

应用程序的配置存储在 `localization_tool_config.json` 文件中。您可以直接编辑此文件，或通过应用程序的 UI 进行配置：

*   **AI 翻译设置**：在 `工具(T) > AI翻译设置...` 中配置 API Key、模型、并发请求数、上下文引用等。
*   **提取规则管理器**：在 `工具(T) > 提取规则管理器...` 中添加、编辑、删除或导入/导出自定义字符串提取规则。
*   **快捷键设置**：在 `设置(S) > 快捷键设置...` 中自定义应用程序的快捷键。

## 📥 下载
**最新版本：v1.0.4**
*   [**Windows (.zip)**](https://github.com/TheSkyC/overwatch-localizer/releases/download/v1.0.4/OverwatchLocalizer-win-x64.zip)
*   [**macOS (.dmg)**](https://github.com/TheSkyC/overwatch-localizer/releases/download/v1.0.4/OverwatchLocalizer-macos-universal.dmg)
*   [**Linux (.tar.gz)**](https://github.com/TheSkyC/overwatch-localizer/releases/download/v1.0.4/OverwatchLocalizer-linux-x64.tar.gz)

## 📸 截图
![image](https://github.com/user-attachments/assets/96f07227-f60b-4dbb-a55f-4eae8918808f)
![image](https://github.com/user-attachments/assets/36f49e65-8c38-4084-b268-9729133a1a8d)

## ⚙️ 部署

### 前提条件

*   Python 3.8 或更高版本
*   Git (可选，用于克隆仓库)

### 步骤

1.  **克隆仓库 (或下载 ZIP)**
    ```bash
    git clone https://github.com/TheSkyC/Overwatch-Localizer.git
    cd Overwatch-Localizer
    ```
    如果您不使用 Git，可以直接下载 ZIP 文件并解压。

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
    激活虚拟环境后，运行：
    ```bash
    python main.py
    ```
2.  **基本工作流程**
    *   **打开代码文件**：点击 `文件(F) > 打开代码文件...` 或将 `.ow` / `.txt` 文件拖放到窗口中。程序将自动提取可翻译字符串。
    *   **打开项目**：点击 `文件(F) > 打开项目...` 或将 `.owproj` 文件拖放到窗口中。这将加载您之前保存的工作。
    *   **翻译**：在左侧的列表中选择一个字符串，然后在右侧的“译文”文本框中输入翻译。
    *   **应用翻译**：输入译文后，点击“应用翻译”按钮，或使用快捷键 `Ctrl+Enter` 应用并跳转到下一个未翻译项。
    *   **保存项目**：点击 `文件(F) > 保存项目` 或 `项目另存为...` 将您的翻译进度保存为 `.owproj` 文件。
    *   **保存翻译到新代码文件**：点击 `文件(F) > 保存翻译到新代码文件` 将翻译后的内容集成回原始代码结构，并保存为新的 `.ow` / `.txt` 文件。

3.  **AI 翻译**
    *   在 `工具(T) > AI翻译设置...` 中配置您的 AI API Key、Base URL 和模型名称。
    *   选择一个或多个字符串，点击 `工具(T) > 使用AI翻译选中项` 或右键菜单中的相应选项。
    *   点击 `工具(T) > 使用AI翻译所有未翻译项` 批量翻译所有未翻译的字符串。

4.  **翻译记忆库 (TM)**
    *   `文件(F) > 导入翻译记忆库 (Excel)`：加载外部 Excel 文件作为翻译记忆库。
    *   `文件(F) > 导出当前记忆库 (Excel)`：将当前内存中的记忆库导出。
    *   `工具(T) > 应用记忆库到未翻译项`：将记忆库中的翻译应用到当前项目中未翻译的字符串。


## 🌐 支持的语言
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
本项目采用 Apache-2.0 许可证。详情请参阅 [LICENSE](LICENSE) 文件。

## 📞 联系

作者：骰子掷上帝 (TheSkyC)
国服ID：小鸟游六花#56683
亚服ID：小鳥游六花#31665
