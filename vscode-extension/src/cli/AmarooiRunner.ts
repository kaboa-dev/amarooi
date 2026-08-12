import { spawn } from "node:child_process";

export interface RunnerResult {
  readonly code: number;
  readonly stdout: string;
  readonly stderr: string;
}

export class AmarooiRunner {
  public constructor(private readonly executable: string = "amarooi") {}

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
}
