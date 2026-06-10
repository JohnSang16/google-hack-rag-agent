import React, { useState, useRef, useEffect, useCallback } from "react";
import { Plus, ChevronDown, ArrowUp, X, FileText, Loader2, Archive } from "lucide-react";

/* --- TYPES --- */
export interface AttachedFile {
  id: string;
  file: File;
  type: string;
  preview: string | null;
  uploadStatus: string;
}

export interface ChatInputModel {
  id: string;
  name: string;
  description: string;
}

export interface ChatInputProps {
  onSendMessage: (message: string, model: string) => void;
  loading?: boolean;
  inputValue?: string;
  onInputValueConsumed?: () => void;
}

/* --- UTILS --- */
const formatFileSize = (bytes: number) => {
  if (bytes === 0) return "0 Bytes";
  const k = 1024;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
};

/* --- FILE PREVIEW CARD --- */
const FilePreviewCard: React.FC<{ file: AttachedFile; onRemove: (id: string) => void }> = ({ file, onRemove }) => {
  const isImage = file.type.startsWith("image/") && file.preview;
  return (
    <div className="relative group flex-shrink-0 w-24 h-24 rounded-xl overflow-hidden border border-bg-300 bg-bg-200 animate-fade-in transition-all hover:border-text-400">
      {isImage ? (
        <div className="w-full h-full relative">
          <img src={file.preview!} alt={file.file.name} className="w-full h-full object-cover" />
          <div className="absolute inset-0 bg-black/20 group-hover:bg-black/0 transition-colors" />
        </div>
      ) : (
        <div className="w-full h-full p-3 flex flex-col justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 bg-bg-300 rounded">
              <FileText className="w-4 h-4 text-text-300" />
            </div>
            <span className="text-[10px] font-medium text-text-400 uppercase tracking-wider truncate">
              {file.file.name.split(".").pop()}
            </span>
          </div>
          <div className="space-y-0.5">
            <p className="text-xs font-medium text-text-200 truncate" title={file.file.name}>{file.file.name}</p>
            <p className="text-[10px] text-text-500">{formatFileSize(file.file.size)}</p>
          </div>
        </div>
      )}
      <button
        onClick={() => onRemove(file.id)}
        className="absolute top-1 right-1 p-1 bg-black/50 hover:bg-black/70 rounded-full text-white opacity-0 group-hover:opacity-100 transition-opacity"
      >
        <X className="w-3 h-3" />
      </button>
      {file.uploadStatus === "uploading" && (
        <div className="absolute inset-0 bg-black/40 flex items-center justify-center">
          <Loader2 className="w-5 h-5 text-white animate-spin" />
        </div>
      )}
    </div>
  );
};

/* --- MODEL SELECTOR --- */
const ModelSelector: React.FC<{
  models: ChatInputModel[];
  selectedModel: string;
  onSelect: (id: string) => void;
}> = ({ models, selectedModel, onSelect }) => {
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const current = models.find((m) => m.id === selectedModel) || models[0];

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setIsOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`inline-flex items-center justify-center shrink-0 transition-colors h-8 rounded-xl px-3 min-w-[4rem] whitespace-nowrap text-xs pl-2.5 pr-2 gap-1
          ${isOpen
            ? "bg-bg-200 text-text-100"
            : "text-text-300 hover:text-text-200 hover:bg-bg-200"}`}
      >
        <span className="font-medium text-[13px]">{current.name}</span>
        <ChevronDown className={`w-4 h-4 opacity-75 transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`} />
      </button>

      {isOpen && (
        <div className="absolute bottom-full right-0 mb-2 w-[240px] bg-bg-100 border border-bg-300 rounded-2xl shadow-2xl overflow-hidden z-50 flex flex-col p-1.5 animate-fade-in">
          {models.map((model) => (
            <button
              key={model.id}
              onClick={() => { onSelect(model.id); setIsOpen(false); }}
              className="w-full text-left px-3 py-2.5 rounded-xl flex items-start justify-between hover:bg-bg-200 transition-colors"
            >
              <div className="flex flex-col gap-0.5">
                <span className="text-[13px] font-semibold text-text-100">{model.name}</span>
                <span className="text-[11px] text-text-400">{model.description}</span>
              </div>
              {selectedModel === model.id && (
                <div className="w-2 h-2 rounded-full bg-accent mt-1.5 flex-shrink-0" />
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

/* --- MAIN COMPONENT --- */
export const ClaudeChatInput: React.FC<ChatInputProps> = ({
  onSendMessage,
  loading = false,
  inputValue,
  onInputValueConsumed,
}) => {
  const [message, setMessage] = useState("");
  const [files, setFiles] = useState<AttachedFile[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [selectedModel, setSelectedModel] = useState("gemini-2.5-flash");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const models: ChatInputModel[] = [
    { id: "gemini-2.5-flash", name: "Gemini 2.5 Flash", description: "Best quality answers" },
    { id: "gemini-2.0-flash", name: "Gemini 2.0 Flash", description: "Faster responses" },
  ];

  // Sync external inputValue (e.g. from suggestion chips)
  useEffect(() => {
    if (inputValue !== undefined && inputValue !== "") {
      setMessage(inputValue);
      textareaRef.current?.focus();
      onInputValueConsumed?.();
    }
  }, [inputValue]);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 384) + "px";
    }
  }, [message]);

  const handleFiles = useCallback((newFilesList: FileList | File[]) => {
    const newFiles = Array.from(newFilesList).map((file) => {
      const isImage = file.type.startsWith("image/") || /\.(jpg|jpeg|png|gif|webp|svg)$/i.test(file.name);
      return {
        id: Math.random().toString(36).substr(2, 9),
        file,
        type: isImage ? "image/unknown" : file.type || "application/octet-stream",
        preview: isImage ? URL.createObjectURL(file) : null,
        uploadStatus: "uploading",
      };
    });
    setFiles((prev) => [...prev, ...newFiles]);
    newFiles.forEach((f) => {
      setTimeout(() => {
        setFiles((prev) => prev.map((p) => (p.id === f.id ? { ...p, uploadStatus: "complete" } : p)));
      }, 800 + Math.random() * 600);
    });
  }, []);

  const onDragOver = (e: React.DragEvent) => { e.preventDefault(); setIsDragging(true); };
  const onDragLeave = (e: React.DragEvent) => { e.preventDefault(); setIsDragging(false); };
  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files) handleFiles(e.dataTransfer.files);
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    const items = e.clipboardData.items;
    const pastedFiles: File[] = [];
    for (let i = 0; i < items.length; i++) {
      if (items[i].kind === "file") {
        const file = items[i].getAsFile();
        if (file) pastedFiles.push(file);
      }
    }
    if (pastedFiles.length > 0) { e.preventDefault(); handleFiles(pastedFiles); }
  };

  const handleSend = () => {
    if ((!message.trim() && files.length === 0) || loading) return;
    onSendMessage(message.trim(), selectedModel);
    setMessage("");
    setFiles([]);
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  const hasContent = message.trim().length > 0 || files.length > 0;

  return (
    <div
      className="relative w-full"
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
    >
      <div className="flex flex-col items-stretch transition-all duration-200 relative z-10 rounded-2xl border border-bg-300 shadow-[0_0_15px_rgba(0,0,0,0.08)] hover:shadow-[0_0_20px_rgba(0,0,0,0.12)] focus-within:shadow-[0_0_25px_rgba(0,0,0,0.15)] bg-bg-100">
        <div className="flex flex-col px-3 pt-3 pb-2 gap-2">

          {/* File previews */}
          {files.length > 0 && (
            <div className="flex gap-3 overflow-x-auto custom-scrollbar pb-2 px-1">
              {files.map((file) => (
                <FilePreviewCard
                  key={file.id}
                  file={file}
                  onRemove={(id) => setFiles((prev) => prev.filter((f) => f.id !== id))}
                />
              ))}
            </div>
          )}

          {/* Textarea */}
          <div className="relative mb-1">
            <div className="max-h-96 w-full overflow-y-auto custom-scrollbar min-h-[2.5rem] pl-1">
              <textarea
                ref={textareaRef}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                onPaste={handlePaste}
                onKeyDown={handleKeyDown}
                placeholder="Ask about your org's history, trends, or plans…"
                disabled={loading}
                className="w-full bg-transparent border-0 outline-none text-text-100 text-[15px] placeholder:text-text-400 resize-none overflow-hidden py-0 leading-relaxed block font-normal disabled:opacity-50"
                rows={1}
                style={{ minHeight: "1.5em" }}
              />
            </div>
          </div>

          {/* Action bar */}
          <div className="flex gap-2 w-full items-center">
            {/* Left: attach */}
            <div className="flex-1 flex items-center shrink min-w-0 gap-1">
              <button
                onClick={() => fileInputRef.current?.click()}
                className="inline-flex items-center justify-center shrink-0 h-8 w-8 rounded-lg transition-colors text-text-400 hover:text-text-200 hover:bg-bg-200"
                type="button"
                aria-label="Attach file"
              >
                <Plus className="w-5 h-5" />
              </button>
            </div>

            {/* Right: model + send */}
            <div className="flex flex-row items-center gap-1">
              <div className="shrink-0 p-1 -m-1">
                <ModelSelector models={models} selectedModel={selectedModel} onSelect={setSelectedModel} />
              </div>
              <button
                onClick={handleSend}
                disabled={!hasContent || loading}
                className={`inline-flex items-center justify-center shrink-0 h-8 w-8 rounded-xl transition-colors active:scale-95
                  ${hasContent && !loading
                    ? "bg-accent text-white hover:bg-accent-hover shadow-md"
                    : "bg-accent/30 text-white/60 cursor-default"}`}
                type="button"
                aria-label="Send"
              >
                <ArrowUp className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Drag overlay */}
      {isDragging && (
        <div className="absolute inset-0 bg-bg-200/90 border-2 border-dashed border-accent rounded-2xl z-50 flex flex-col items-center justify-center backdrop-blur-sm pointer-events-none">
          <Archive className="w-10 h-10 text-accent mb-2 animate-bounce" />
          <p className="text-accent font-medium text-sm">Drop files to attach</p>
        </div>
      )}

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        className="hidden"
        onChange={(e) => { if (e.target.files) handleFiles(e.target.files); e.target.value = ""; }}
      />
    </div>
  );
};

export default ClaudeChatInput;
