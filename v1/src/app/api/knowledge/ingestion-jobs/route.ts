import { auth } from "../../../../../auth";
import { jsonResponse } from "@/lib/agent-studio-proxy";
import {
  extensionOf,
  KNOWLEDGE_UPLOAD_LIMITS,
  proxyAgentStudioJson,
} from "@/lib/knowledge-proxy";

interface KnowledgeUploadFilePayload {
  filename: string;
  content: string;
  encoding: "base64";
  category?: string;
  source_path?: string;
  metadata: Record<string, unknown>;
}

function textField(form: FormData, name: string, fallback: string): string {
  const value = form.get(name);
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
}

function optionalTextField(form: FormData, name: string): string | undefined {
  const value = form.get(name);
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

export async function GET(): Promise<Response> {
  const session = await auth();
  if (!session?.user?.id) {
    return jsonResponse({ detail: "Authentication required." }, 401);
  }

  return proxyAgentStudioJson(session, "/knowledge/ingestion-jobs");
}

export async function POST(request: Request): Promise<Response> {
  const session = await auth();
  if (!session?.user?.id) {
    return jsonResponse({ detail: "Authentication required." }, 401);
  }

  const form = await request.formData();
  const files = form
    .getAll("files")
    .filter((value): value is File => value instanceof File && value.size > 0);

  if (files.length === 0) {
    return jsonResponse({ detail: "At least one file is required." }, 400);
  }

  if (files.length > KNOWLEDGE_UPLOAD_LIMITS.maxFiles) {
    return jsonResponse(
      { detail: `Upload at most ${KNOWLEDGE_UPLOAD_LIMITS.maxFiles} files per ingestion job.` },
      400,
    );
  }

  const category = optionalTextField(form, "category");
  const payloadFiles: KnowledgeUploadFilePayload[] = [];

  for (const file of files) {
    if (file.size > KNOWLEDGE_UPLOAD_LIMITS.maxBytesPerFile) {
      return jsonResponse(
        { detail: `${file.name} is larger than the 10 MB upload limit.` },
        400,
      );
    }

    const extension = extensionOf(file.name);
    if (!KNOWLEDGE_UPLOAD_LIMITS.allowedExtensions.has(extension)) {
      return jsonResponse(
        { detail: `${file.name} is not a supported knowledge file type.` },
        400,
      );
    }

    const buffer = Buffer.from(await file.arrayBuffer());
    payloadFiles.push({
      filename: file.name,
      content: buffer.toString("base64"),
      encoding: "base64",
      category,
      metadata: {
        upload_size_bytes: file.size,
        upload_type: file.type || "application/octet-stream",
      },
    });
  }

  return proxyAgentStudioJson(session, "/knowledge/ingestion-jobs", {
    method: "POST",
    body: JSON.stringify({
      source_name: textField(form, "source_name", "Manual Upload"),
      source_type: textField(form, "source_type", "manual_upload"),
      files: payloadFiles,
      metadata: {
        submitted_from: "sagad_console",
      },
    }),
  });
}
