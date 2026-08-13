import { spawn } from "node:child_process";
import * as vscode from "vscode";

export interface RunnerResult {
  readonly code: number;
  readonly stdout: string;
  readonly stderr: string;
}

export class AmarooiRunner {
  public constructor(private readonly executable: string = "amarooi") {}

  /**
   * Verify that the Amarooi CLI exists on the system PATH.
   *
   * When the CLI is not found the user is offered a VS Code notification with
   * an action to install it via `pip install amarooi`.
   *
   * @returns `true` when the CLI is available, `false` otherwise.
   */
  public async ensureCliAvailable(): Promise<boolean> {
    const available = await this._checkCliOnPath();
    if (!available) {
      const action = "Install via pip";
      const selection = await vscode.window.showWarningMessage(
        "The Amarooi CLI was not found on your PATH.  " +
          "Install it to use Amarooi features.",
        action
      );
      if (selection === action) {
        await this._runPipInstall();
      }
    }
    return available;
  }

  public runArchitect(prompt: string, cwd?: string): Promise<RunnerResult> {
    return this.run(["architect", "--prompt", prompt], cwd);
  }

  public transpileFile(inputPath: string, outputPath: string, cwd?: string): Promise<RunnerResult> {
    return this.run(["transpile", "--file", inputPath, "--out", outputPath], cwd);
  }

  private run(args: readonly string[], cwd?: string): Promise<RunnerResult> {
    return new Promise<RunnerResult>((resolve, reject) => {
      const child = spawn(this.executable, args, {
        cwd,
        shell: false,
      });

      let stdout = "";
      let stderr = "";

      child.stdout.on("data", (chunk: Buffer | string) => {
        stdout += chunk.toString();
      });

      child.stderr.on("data", (chunk: Buffer | string) => {
        stderr += chunk.toString();
      });

      child.on("error", (error: Error) => {
        reject(error);
      });

      child.on("close", (code: number | null) => {
        resolve({
          code: code ?? 1,
          stdout,
          stderr,
        });
      });
    });
  }

  /** Check whether `amarooi` resolves on the system PATH. */
  private _checkCliOnPath(): Promise<boolean> {
    const checkCmd = process.platform === "win32" ? "where" : "which";
    return new Promise<boolean>((resolve) => {
      const child = spawn(checkCmd, [this.executable], { shell: false });
      child.on("close", (code) => resolve(code === 0));
      child.on("error", () => resolve(false));
    });
  }

  /** Run `pip install amarooi` in a VS Code terminal so the user can follow progress. */
  private async _runPipInstall(): Promise<void> {
    const terminal = vscode.window.createTerminal("Amarooi Installer");
    terminal.show(true);
    terminal.sendText("pip install amarooi", true);
  }
}
