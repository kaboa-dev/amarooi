import * as vscode from "vscode";
import * as fs from "node:fs/promises";
import * as os from "node:os";
import * as path from "node:path";

import { AmarooiRunner } from "../cli/AmarooiRunner";
import { ExtensionMessage, isWebviewMessage } from "../messaging/types";
import { getArchitectHtml } from "./getArchitectHtml";

export class ArchitectPanel {
  private static readonly viewType = "amarooi.architectPanel";

  public static createOrShow(extensionUri: vscode.Uri, runner: AmarooiRunner): void {
    const panel = vscode.window.createWebviewPanel(
      ArchitectPanel.viewType,
      "Amarooi SDLC Architect",
      vscode.ViewColumn.One,
      {
        enableScripts: true,
      }
    );

    const architectPanel = new ArchitectPanel(panel, extensionUri, runner);
    architectPanel.initialize();
  }

  private constructor(
    private readonly panel: vscode.WebviewPanel,
    private readonly extensionUri: vscode.Uri,
    private readonly runner: AmarooiRunner
  ) {}

  private initialize(): void {
    this.panel.webview.html = getArchitectHtml(this.panel.webview, this.extensionUri, this.createNonce());

    this.panel.webview.onDidReceiveMessage(async (message: unknown) => {
      if (!isWebviewMessage(message)) {
        this.postMessage({ event: "error", content: "Invalid message received from webview." });
        return;
      }

      try {
        switch (message.command) {
          case "preview": {
            if (!message.draft.trim()) {
              this.postMessage({ event: "error", content: "Generate pseudocode before previewing transpiled output." });
              return;
            }

            await this.transpileDraft(message.draft);
            return;
          }
          case "generate": {
            await vscode.window.withProgress(
              {
                location: vscode.ProgressLocation.Window,
                title: "Running Amarooi architect",
                cancellable: false,
              },
              async () => {
                const result = await this.runner.runArchitect(message.prompt, this.workspacePath());
                const content = result.stdout || message.draft;

                if (result.code !== 0) {
                  this.postMessage({ event: "error", content: result.stderr || "Architect command failed." });
                  return;
                }

                this.postMessage({ event: "generated", content });
              }
            );
            return;
          }
          case "error": {
            vscode.window.showErrorMessage(message.error);
            return;
          }
          default: {
            this.postMessage({ event: "error", content: "Unsupported command." });
          }
        }
      } catch (error) {
        const renderedError = error instanceof Error ? error.message : "Unknown error";
        this.postMessage({ event: "error", content: renderedError });
      }
    });
  }

  public async transpileDraft(draft: string): Promise<void> {
    await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Window,
        title: "Transpiling draft with Amarooi",
        cancellable: false,
      },
      async () => {
        const tempDir = await fs.mkdtemp(path.join(os.tmpdir(), "amarooi-vscode-"));
        const inputPath = path.join(tempDir, "draft.amarooi");
        const outputPath = path.join(tempDir, "draft.py");

        await fs.writeFile(inputPath, draft, { encoding: "utf-8" });
        const result = await this.runner.transpileFile(inputPath, outputPath, this.workspacePath());

        if (result.code !== 0) {
          this.postMessage({ event: "error", content: result.stderr || "Transpile command failed." });
          return;
        }

        const transpiled = await fs.readFile(outputPath, { encoding: "utf-8" });
        this.postMessage({ event: "preview", content: transpiled });
      }
    );
  }

  private workspacePath(): string | undefined {
    return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  }

  private postMessage(message: ExtensionMessage): void {
    void this.panel.webview.postMessage(message);
  }

  private createNonce(): string {
    const characters = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
    let value = "";
    for (let i = 0; i < 32; i += 1) {
      value += characters.charAt(Math.floor(Math.random() * characters.length));
    }

    return value;
  }
}
