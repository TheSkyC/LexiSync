<div align="center">

![GitHub release (latest by date)](https://img.shields.io/github/v/release/TheSkyC/LexiSync?style=flat-square)
![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)
![Python Version](https://img.shields.io/badge/Python-3.8%2B-blue?style=flat-square&logo=python)
</div>
  <p align="center"><a href="../README.md">中文</a> | <a href="./README.en.md">English</a> | 日本語<br></p>

# LexiSync
**LexiSync** は、強力なデスクトップアプリケーションです。テキストのスマート抽出から、AI翻訳支援、データ駆動型の品質保証に至るまで、包括的かつ効率的なローカライズソリューションを提供し、多言語コンテンツの管理プロセスを大幅に簡素化します。

本ツールは業界標準の PO/POT ファイルと完全な互換性があり、さらに『オーバーウォッチ』ワークショップコードの翻訳もサポートしているため、汎用的なローカライズ編集・管理プラットフォームとして利用できます。

---

## 📥 ダウンロード
最新バージョンは **[GitHub Releases](https://github.com/TheSkyC/LexiSync/releases/latest)** ページからダウンロードできます。

[![GitHub release (latest by date)](https://img.shields.io/github/v/release/TheSkyC/LexiSync?style=for-the-badge)](https://github.com/TheSkyC/LexiSync/releases/latest)


## 🚀 主な機能

### 📂 プロジェクト管理システム
*   **複数ファイル対応**：1つのプロジェクト内で複数のソースファイルを同時に管理できます。
*   **プロジェクト構造**：バージョン管理に適した明確なアーキテクチャを採用しています。
*   **スマート再スキャン**：ソースファイルが更新された際、変更をスマートに検出します。
*   **ワンクリックビルド**：全自動のビルドプロセスにより、ワンクリックですべてのターゲット言語の翻訳済みファイルを生成します。

### 🖥️ モダンなインタラクティブ・インターフェース
*   **デュアルトラック・マーカーバー**：
    *   **ポイントマーカー**：スクロールバーの左側に、エラー、警告、検索結果を直感的に表示します。
    *   **範囲マーカー**：右側に、現在の選択範囲やGitの変更ステータス（追加/修正）を表示します。
    *   **インタラクション**：詳細のホバープレビュー（ツールチップ）やクリックによるジャンプ機能をサポートしています。
*   **コンテキストプレビュー**：翻訳時にコードやPOファイルのコンテキスト行をリアルタイムで表示し、キーワードのハイライトや正確な位置特定をサポートします。

### 🤖 AIと自動化
*   **スマートテキスト抽出**：カスタマイズ可能な正規表現を使用して、コードファイルから翻訳可能な文字列を自動的に抽出します。
*   **AI翻訳支援**：OpenAI APIを統合し、単一または一括翻訳をサポートします。プレースホルダーをスマートに識別し、プロジェクトの用語集やコンテキスト情報を引用できます。
*   **自動QA**：
    *   **リアルタイム検証**：入力時に、プレースホルダーの欠落、句読点の不一致、先頭・末尾のスペースなどのエラーを即座に検出します。
    *   **膨張率チェック**：ビッグデータモデルに基づいて、翻訳の長さの異常を検出します。

### 🛠️ 高度なカスタマイズ性
アプリケーションの設定はルートディレクトリの `config.json` ファイルに保存されます。以下のUIから設定可能です：
*   **AI翻訳設定**: `ツール(T) > AI翻訳設定...`
*   **抽出ルールマネージャー**: `ツール(T) > 抽出ルールマネージャー...`
*   **ショートカットキー設定**: `設定(S) > ショートカットキー設定...`
*   **フォント設定**: `設定(S) > フォント設定...`


## 📸 スクリーンショット
*メイン画面*

<img width="800" height="600" alt="image" src="https://github.com/user-attachments/assets/3d45751c-1b48-47a9-9a9c-df3f62a6d912" />
<img width="800" height="600" alt="image" src="https://github.com/user-attachments/assets/8fc10914-0417-4165-b2ae-874fa433963d" />


<details>
<summary><b>► クリックしてスクリーンショットをもっと見る</b></summary>

*AI設定のカスタマイズ*

<img width="800" height="700" alt="image" src="https://github.com/user-attachments/assets/71384ff5-cd27-415f-b549-31ffec65c5cc" />

*プロジェクト統計*

<img width="800" height="600" alt="image" src="https://github.com/user-attachments/assets/4d6cf519-d5c9-4269-ba40-bd567854e0b1" />

*言語ペア設定*

<img width="550" height="680" alt="image" src="https://github.com/user-attachments/assets/4a353f79-7b3f-445f-9c94-b4027f6fea73" />

*プラグイン設定*

<img width="800" height="600" alt="image" src="https://github.com/user-attachments/assets/9ac8965e-c980-43e1-9961-99c4033affcf" />
</details>


## 🛠️ 開発環境のセットアップ

### 前提条件
*   Python 3.8 以降
*   Git (オプション、リポジトリのクローン用)

### 手順
1.  **リポジトリのクローン (またはZIPのダウンロード)**
    ```bash
    git clone https://github.com/TheSkyC/LexiSync.git
    cd LexiSync
    ```

2.  **仮想環境の作成と有効化 (推奨)**
    ```bash
    python -m venv venv
    # Windows
    .\venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```

3.  **依存関係のインストール**
    ```bash
    pip install -r requirements.txt
    ```

4.  **実行**
    ```bash
    python main.py
    ```

## 🚀 クイックスタート

LexiSyncは、さまざまな使用シナリオに合わせて2つの柔軟な作業モードを提供します：

### 1. ⚡ クイック編集モード
*単一ファイルの素早い修正、一時的な閲覧、または軽量なタスクに適しています。*

1.  **開く**: 単一のソースファイルをメイン画面に直接ドラッグするか、メニューバーの `ファイル > ファイルを開く` をクリックします。
2.  **翻訳**: 通常通り、AI支援や用語集のヒントを利用して翻訳します。
3.  **保存**: `Ctrl+S` を押して変更を直接保存します。

### 2. 📂 プロジェクトモード
*長期的なメンテナンスやバージョン管理が必要な、複数ファイル・多言語の大規模プロジェクトに適しています。*

1.  **プロジェクト作成**: `新規プロジェクト` (Ctrl+Shift+N) をクリックし、ソースファイルを一括でドラッグします。また、`.tbx` や `.xlsx` ファイルを直接ドラッグして、プロジェクト専用の用語集や翻訳メモリをバインドすることもできます。
2.  **管理と翻訳**: 左側のファイルエクスプローラーでダブルクリックして、異なるソースファイルをシームレスに切り替えます。右側の**マーカーバー** (MarkerBar) を利用して、エラー、警告、現在の編集位置を素早く特定します。
3.  **ビルドと納品**: 確認後、`ファイル > プロジェクトをビルド` (Ctrl+B) をクリックします。プログラムはバックグラウンドですべてのターゲット言語の翻訳済み最終ファイルを自動生成し、`target/` ディレクトリに整理して出力します。

## 🌐 対応言語
本ツールはあらゆる言語の翻訳に対応しており、以下の言語についてはUIのローカライズが提供されています：
*   **English** (`en_US`)
*   **简体中文** (`zh_CN`)
*   **日本語** (`ja_JP`)
*   **한국어** (`ko_KR`)
*   **le français** (`fr_FR`)
*   **Deutsch** (`de_DE`)
*   **русский язык** (`ru_RU`)
*   **español (España)** (`es_ES`)
*   **italiano** (`it_IT`)

## 🤝 貢献
どのような形での貢献も歓迎します！質問、機能の提案、またはバグの発見がありましたら、お気軽に GitHub Issues から送信してください。

## 📄 ライセンス
本プロジェクトは [Apache 2.0](LICENSE) ライセンスの下でオープンソース化されており、著作権表示を保持することを条件に、自由に使用、修正、配布することができます。

## 📞 連絡先
- 作者：TheSkyC
- メール：0x4fe6@gmail.com
