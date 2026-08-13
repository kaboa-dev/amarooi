import * as vscode from "vscode";

export function getArchitectHtml(webview: vscode.Webview, extensionUri: vscode.Uri, nonce: string): string {
  const toolkitUri = webview.asWebviewUri(
    vscode.Uri.joinPath(extensionUri, "node_modules", "@vscode", "webview-ui-toolkit", "dist", "toolkit.js")
  );
  const stylesUri = webview.asWebviewUri(
    vscode.Uri.joinPath(extensionUri, "src", "webview", "styles.css")
  );

  return `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Amarooi SDLC Architect Wizard</title>
    <link rel="stylesheet" href="${stylesUri}" />
  </head>
  <body>
    <div class="layout">
      <section class="panel" aria-label="Interviewer">
        <h2>The Interviewer</h2>
        <div id="chatLog" class="chat-log" role="log" aria-live="polite"></div>
        <div class="row">
          <vscode-text-field id="answerInput" placeholder="Answer the architect's question..."></vscode-text-field>
          <vscode-button id="generateButton">Generate</vscode-button>
        </div>
      </section>

      <section class="panel" aria-label="Live Preview">
        <h2>Live Preview</h2>
        <vscode-text-area id="previewArea" readonly resize="vertical"></vscode-text-area>
        <div class="actions">
          <vscode-button id="previewButton" appearance="secondary">Preview</vscode-button>
        </div>
      </section>
    </div>

    <script type="module" nonce="${nonce}" src="${toolkitUri}"></script>
    <script nonce="${nonce}">
      const vscode = acquireVsCodeApi();
      const chatLog = document.getElementById("chatLog");
      const answerInput = document.getElementById("answerInput");
      const previewArea = document.getElementById("previewArea");
      const generateButton = document.getElementById("generateButton");
      const previewButton = document.getElementById("previewButton");

      const appendMessage = (label, text) => {
        const row = document.createElement("p");
        row.textContent = label + ": " + text;
        chatLog.appendChild(row);
        chatLog.scrollTop = chatLog.scrollHeight;
      };

      generateButton.addEventListener("click", () => {
        const prompt = String(answerInput.value || "").trim();
        if (!prompt) {
          vscode.postMessage({ command: "error", error: "Please enter a prompt before generating." });
          return;
        }

        appendMessage("You", prompt);
        vscode.postMessage({
          command: "generate",
          prompt,
          draft: String(previewArea.value || ""),
        });
      });

      previewButton.addEventListener("click", () => {
        vscode.postMessage({
          command: "preview",
          draft: String(previewArea.value || ""),
        });
      });

      window.addEventListener("message", (event) => {
        const message = event.data;
        if (!message || typeof message !== "object") {
          return;
        }

        if (message.event === "preview") {
          previewArea.value = message.content;
          return;
        }

        if (message.event === "generated") {
          appendMessage("Amarooi", "Generation completed.");
          previewArea.value = message.content;
          return;
        }

        if (message.event === "error") {
          appendMessage("Error", message.content);
        }
      });
    </script>
  </body>
</html>`;
}
