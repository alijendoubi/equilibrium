import { ImageResponse } from "next/og";

export const OG_SIZE = { width: 1200, height: 630 };
export const OG_CONTENT_TYPE = "image/png";

// Generated images cannot read CSS variables: these mirror the light-theme tokens in globals.css.
const BG = "#fbfbf9";
const FG = "#16181d";
const MUTED = "#5b6170";
const CLUSTER = "#0f766e";
const BORDER = "#e3e5ea";

export interface OgCardProps {
  eyebrow: string;
  title: string;
  /** One sourced link, e.g. "caused by GBA1 · curated · confidence 0.95". */
  detail?: string;
}

/** The shared 1200x630 share card: eyebrow, title, one sourced fact, the evidence promise. */
export function ogCard({ eyebrow, title, detail }: OgCardProps): ImageResponse {
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        padding: "72px 80px",
        background: BG,
        color: FG,
        fontFamily: "sans-serif",
      }}
    >
      <div style={{ display: "flex", flexDirection: "column" }}>
        <div style={{ fontSize: 26, fontWeight: 700, letterSpacing: 4, color: CLUSTER }}>
          {eyebrow.toUpperCase()}
        </div>
        <div
          style={{
            marginTop: 28,
            fontSize: title.length > 48 ? 58 : 72,
            fontWeight: 700,
            lineHeight: 1.05,
          }}
        >
          {title}
        </div>
        {detail && (
          <div
            style={{
              marginTop: 36,
              display: "flex",
              alignItems: "center",
              fontSize: 30,
              color: MUTED,
            }}
          >
            <div
              style={{
                width: 56,
                height: 6,
                background: CLUSTER,
                borderRadius: 3,
                marginRight: 20,
              }}
            />
            {detail}
          </div>
        )}
      </div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          borderTop: `2px solid ${BORDER}`,
          paddingTop: 28,
          fontSize: 26,
          color: MUTED,
        }}
      >
        <div style={{ fontWeight: 700, color: FG }}>Equilibrium</div>
        <div>Every line is a sourced claim</div>
      </div>
    </div>,
    OG_SIZE,
  );
}
