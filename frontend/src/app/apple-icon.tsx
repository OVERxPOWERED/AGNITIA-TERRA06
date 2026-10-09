import { ImageResponse } from "next/og";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", background: "#1e5a43", borderRadius: 40 }}>
        <svg width="120" height="120" viewBox="0 0 32 32">
          <path d="M8 8.5 L15.2 24" stroke="#f6faf7" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
          <path d="M24.5 8 L17.2 15.2 H21.4 L15.2 24" stroke="#f6faf7" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
        </svg>
      </div>
    ),
    size,
  );
}
