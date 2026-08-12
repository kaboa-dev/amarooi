import * as vscode from "vscode";

import { AmarooiRunner } from "./cli/AmarooiRunner";
import { ArchitectPanel } from "./panels/ArchitectPanel";

export function activate(context: vscode.ExtensionContext): void {
  const runner = new AmarooiRunner();

  const openWizard = vscode.commands.registerCommand("amarooi.startWizard", () => {
    ArchitectPanel.createOrShow(context.extensionUri, runner);
  });

  const transpileFile = vscode.commands.registerCommand(
    "amarooi.transpileFile",
    async (uri?: vscode.Uri) => {
      const target = uri ?? vscode.window.activeTextEditor?.document.uri;

      if (!target || target.fsPath.toLowerCase().endsWith(".amarooi") === false) {
        vscode.window.showErrorMessage("Please select an .amarooi file to transpile.");
        return;
      }

      const outputPath = target.fsPath.replace(/\.amarooi$/i, ".py");

      await vscode.window.withProgress(
        {
          location: vscode.ProgressLocation.Window,
          title: "Transpiling .amarooi file",
          cancellable: false,
        },
        async () => {
          const result = await runner.transpileFile(target.fsPath, outputPath, vscode.workspace.workspaceFolders?.[0]?.uri.fsPath);
          if (result.code !== 0) {
            vscode.window.showErrorMessage(result.stderr || "Transpile command failed.");
            return;
          }

          vscode.window.showInformationMessage(`Transpiled to ${outputPath}`);
        }
      );
    }
  );

  context.subscriptions.push(openWizard, transpileFile);
}

export function deactivate(): void {
  // no-op
}
