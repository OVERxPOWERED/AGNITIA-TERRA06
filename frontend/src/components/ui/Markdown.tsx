"use client";
/** Renders the markdown documents the API serves (assumptions, calibration, real-data results). */
import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function Markdown({ children }: { children: string }) {
  return (
    <div className="max-w-[78ch] break-words text-[14px] leading-relaxed text-ink [&>*:first-child]:mt-0">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: (p) => <h3 className="mb-2 mt-6 text-[17px] font-semibold tracking-tight" {...p} />,
          h2: (p) => <h3 className="mb-2 mt-6 text-[16px] font-semibold tracking-tight" {...p} />,
          h3: (p) => <h4 className="mb-1.5 mt-5 text-[14px] font-semibold" {...p} />,
          h4: (p) => <h4 className="mb-1.5 mt-4 text-[14px] font-semibold" {...p} />,
          p: (p) => <p className="my-3 text-ink/90" {...p} />,
          ul: (p) => <ul className="my-3 list-disc space-y-1 pl-5" {...p} />,
          ol: (p) => <ol className="my-3 list-decimal space-y-1 pl-5" {...p} />,
          a: (p) => <a className="text-accent underline underline-offset-2" {...p} />,
          blockquote: (p) => <blockquote className="my-3 border-l-2 border-line-strong pl-4 text-muted" {...p} />,
          hr: () => <hr className="my-6 border-line" />,
          table: ({ children: ch }) => (
            <div className="my-4 w-full overflow-x-auto rounded-lg border border-line">
              <table className="w-full border-collapse text-[13px]">{ch}</table>
            </div>
          ),
          th: (p) => <th className="whitespace-nowrap border-b border-line bg-sunken px-3 py-2 text-left text-[12px] font-medium text-muted" {...p} />,
          td: (p) => <td className="num border-b border-line/70 px-3 py-2 align-top" {...p} />,
          pre: (p) => <pre className="my-3 max-w-full overflow-x-auto rounded-lg border border-line bg-sunken p-3 text-[12px]" {...p} />,
          code: ({ className, children: ch, ...rest }) => (
            <code className={`${className ?? ""} num rounded bg-sunken px-1 py-0.5 text-[12px]`} {...rest}>{ch}</code>
          ),
          img: ({ src, alt }) => {
            const s = typeof src === "string" ? src : "";
            // eslint-disable-next-line @next/next/no-img-element
            return <img src={s.startsWith("/") ? s : `/${s}`} alt={alt ?? ""} className="my-3 h-auto max-w-full rounded-lg border border-line" />;
          },
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
