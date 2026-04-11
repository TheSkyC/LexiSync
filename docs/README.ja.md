<div align="center">

![LexiSync Logo](https://img.shields.io/badge/LexiSync-409EFF?style=for-the-badge&logo=sync)

![GitHub release (latest by date)](https://img.shields.io/github/v/release/TheSkyC/LexiSync?style=flat-square)
![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)
![Python Version](https://img.shields.io/badge/Python-3.12%2B-blue?style=flat-square&logo=python)
![Vue Version](https://img.shields.io/badge/Vue.js-3.x-4FC08D?style=flat-square&logo=vuedotjs)
</div>
<p align="center"><a href="../README.md">English</a> | <a href="./README.zh.md">中文</a> | 日本語<br></p>

# LexiSync
**LexiSync** は、開発者、翻訳者、チーム向けの次世代ローカリゼーションコラボレーションプラットフォームです。強力なデスクトップパフォーマンスとリアルタイムのWebクラウドコラボレーションをシームレスに組み合わせ、テキスト抽出、AI支援翻訳、品質保証からマルチデバイス同期までの完全なソリューションを提供します。

コード内の文字列をすばやく処理する個人開発者であっても、複雑な多言語プロジェクトを共同で翻訳する分散チームであっても、LexiSyncはワークフローを大幅に簡素化します。

---

## 📥 ダウンロード
Windows、macOS、Linux向けの最新バージョンは、**[GitHub Releases](https://github.com/TheSkyC/LexiSync/releases/latest)** ページからダウンロードできます。

[![GitHub release (latest by date)](https://img.shields.io/github/v/release/TheSkyC/LexiSync?style=for-the-badge)](https://github.com/TheSkyC/LexiSync/releases/latest)

## 🚀 主な機能

### ☁️ クラウドリアルタイムコラボレーション (Cloud Collaboration)
*   **ワンクリックホスティング**: ローカルプロジェクトをワンクリックでサーバーとして公開します。チームメンバーはクライアントをインストールすることなく、ブラウザ（Web UI）経由で直接参加できます。
*   **マルチデバイスリアルタイム同期**: 翻訳、ステータス（レビュー済み/あいまい）、コメントの変更は、ミリ秒単位ですべてのオンラインメンバーにブロードキャストされます。Web上での共同の元に戻す/やり直しをサポートします。
*   **コラボレーション認識と競合防止**: 他のメンバーが編集しているエントリをリアルタイムで表示します（カーソルロック）。組み込みのMyers diffアルゴリズムにより、同時編集の競合をエレガントに解決します。
*   **トンネリングとセキュリティ**: Cloudflare Tunnelをネイティブに統合し、パブリックIPなしで安全なパブリックアクセスリンクを生成します。ロールベースのアクセス制御（RBAC）、きめ細かいスコープ制限、IP禁止、永続的な監査ログが組み込まれています。

### 📂 包括的なフォーマットサポート (25+ Formats)
*   **膨大なフォーマット互換性**: 25以上の業界標準、主流フレームワーク、マルチメディア、およびオフィスドキュメントのローカリゼーションファイルをネイティブにサポートします。
    *   **業界標準とデスクトップUI**: `PO/POT`, `XLIFF`, `Qt TS`
    *   **モバイルとクロスプラットフォーム**: `Android Strings (XML)`, `iOS/macOS (.strings, .stringsdict)`, `Xcode String Catalog (.xcstrings)`, `Flutter ARB`
    *   **データシリアル化と設定**: `JSON`, `i18next JSON`, `YAML`, `TOML`, `INI`
    *   **デスクトップとバックエンド**: `Java .properties`, `.NET RESX`, `PHP Array`, `Windows RC`
    *   **テーブルとバッチ処理**: `CSV`, `Excel (.xlsx)`
    *   **マルチメディアと字幕**: `SRT`, `VTT`
    *   **Webとリッチオフィスドキュメント**: `HTML`, `Markdown/MDX`, `Word (.docx)`, `PowerPoint (.pptx)`
    *   **カスタムおよび特殊フォーマット**: `Mozilla Fluent (.ftl)`, `OwCode(.ow)`
*   **ネイティブ複数形サポート**: 各言語の複数形ルール（Zero/One/Two/Few/Many/Other）をサポートします。AI翻訳および検証エンジンは、複数形のコンテキストに完全に適応しています。

### 🤖 AI駆動のスマートワークフロー
*   **スマート一括翻訳**: 翻訳前にすべてのテキストを深く分析し、**スタイルガイド**を自動生成し、**主要な用語**を抽出し、**翻訳メモリ (TM)** と**セマンティック検索 (RAG)** を組み合わせてAIに豊富なコンテキストを提供することで、翻訳の品質と一貫性を大幅に向上させます。
*   **インタラクティブレビューモード**: まったく新しい半自動ワークフロー。AIがバックグラウンドで事前翻訳を行い、ユーザーはUIでエントリを1つずつ確認、修正、またはスキップするだけで、効率と手動制御のバランスを取ることができます。
*   **自動QA**: 入力時にプレースホルダーの欠落、句読点の不一致、先頭/末尾のスペースなどのエラーをリアルタイムで検出します。ワンクリックの「自動修正」または「AI修正」をサポートします。

### 🖥️ モダンなインタラクティブインターフェース
*   **デスクトップ**: デュアルトラックマーカーバー（エラー、警告、検索結果を直感的に表示）、リアルタイムのコンテキストプレビュー、インタラクティブな履歴パネル。
*   **Web**: Vue 3で構築されたレスポンシブインターフェース。ダークモードと組み込みのリアルタイムチャットドロワーをサポートします。

## 📸 スクリーンショット

*デスクトップのメインインターフェース*

<img width="800" alt="Desktop UI" src="assets/ui-desktop.png" />

*Webリアルタイムコラボレーション*

<img width="800" alt="Web UI" src="assets/ui-web.png" />

<details>
<summary><b>► クリックして他のスクリーンショットを表示</b></summary>

*ウェルカム画面とフォーマット*

<img width="800" alt="Welcome Screen & Formats" src="assets/ui-welcome.png" />

*スマート翻訳*

<img width="800" alt="Smart Translation" src="assets/feature-smart-translation.png" />

*AIモデル管理*

<img width="800" alt="AI Models Management" src="assets/feature-ai-models.png" />

*プラグイン管理*

<img width="800" alt="Plugins Management" src="assets/feature-plugins.png" />

</details>

## 🛠️ 開発環境のセットアップ

### 前提条件
*   Python 3.12 以上
*   Node.js 20.x 以上 (Webフロントエンドのビルド用)
*   Git (オプション、リポジトリのクローン用)

### 手順
1.  **リポジトリのクローン (またはZIPのダウンロード)**
    ```bash
    git clone https://github.com/TheSkyC/LexiSync.git
    cd LexiSync
    ```

2.  **仮想環境の作成とアクティブ化 (推奨)**
    ```bash
    python -m venv venv
    # Windows
    .\venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```

3.  **Python依存関係のインストール**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Webフロントエンドのビルド**
    ```bash
    cd web_src
    npm ci
    npm run build
    cd ..
    ```

5.  **アプリケーションの実行**
    ```bash
    python src/lexisync/main.py
    ```

## 🚀 クイックスタート

LexiSyncは、さまざまなシナリオに合わせて3つの柔軟な作業モードを提供します。

### 1. ⚡ クイック編集モード (単一ファイル)
*迅速な変更、一時的な表示、または軽量なタスクに最適です。*
*   単一のファイル（例：`.po`, `.json`, `.strings`）をメインインターフェースに直接ドラッグ＆ドロップします。
*   通常通り、AI支援と用語のヒントを使用して翻訳します。
*   `Ctrl+S` を押して変更を直接保存します。

### 2. 📂 プロジェクトモード (ローカル複数ファイル)
*複数のファイルや言語にまたがる長期的なメンテナンスとバージョン管理が必要な大規模プロジェクトに最適です。*
*   `新規プロジェクト` (Ctrl+Shift+N) をクリックし、ソースファイルをまとめてドラッグします。
*   左側のファイルブラウザでダブルクリックすると、異なるソースファイル間をシームレスに切り替えることができます。
*   確認後、`ファイル > プロジェクトのビルド` (Ctrl+B) をクリックすると、プログラムがすべてのターゲット言語の最終的な翻訳済みファイルを自動的に生成します。

### 3. ☁️ クラウドコラボレーションモード (チームマルチクライアント)
*複数の人が同時に翻訳やレビューを行う必要があるチームプロジェクトに最適です。*
*   クイック/プロジェクトモードで、下部の **「クラウドコラボレーション (Cloud Collaboration)」** パネルを開きます。
*   **「クラウドサービスを開始」** をクリックします。外部アクセスが必要な場合は、設定で「パブリックURLを有効にする (トンネリング)」をオンにします。
*   「ユーザーと権限の管理」でチームメンバー専用のアクセスTokenを生成します。
*   メンバーはブラウザ経由で生成されたリンクにアクセスすることで、リアルタイムコラボレーションに参加できます。

## 🌐 サポートされているUI言語
このツールは任意の言語への翻訳をサポートしており、以下の言語のUIインターフェースを提供しています。
*   **English** (`en_US`)
*   **简体中文** (`zh_CN`)
*   **日本語** (`ja_JP`)
*   **한국어** (`ko_KR`)
*   **Français** (`fr_FR`)
*   **Deutsch** (`de_DE`)
*   **Русский** (`ru_RU`)
*   **Español (España)** (`es_ES`)
*   **Italiano** (`it_IT`)

## 🤝 貢献
あらゆる形の貢献を歓迎します！質問、機能の提案、またはバグを見つけた場合は、GitHub Issuesからお気軽にお知らせください。

## 📄 ライセンス
このプロジェクトは [Apache 2.0](../LICENSE) ライセンスの下でオープンソース化されており、著作権表示を保持することを条件に、自由な使用、変更、配布が許可されています。

## 📞 連絡先
- 著者：骰子掷上帝 (TheSkyC)
- メール：0x4fe6@gmail.com