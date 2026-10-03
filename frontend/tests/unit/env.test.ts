import { describe, expect, it } from "vitest";
import { DEFAULT_BACKEND_URL, getPublicEnv, getServerEnv } from "@/lib/env";

describe("env", () => {
  it("defaults both URLs to localhost:8000 when unset", () => {
    expect(getPublicEnv({}).NEXT_PUBLIC_API_URL).toBe(DEFAULT_BACKEND_URL);
    expect(getServerEnv({}).BACKEND_URL).toBe("http://localhost:8000");
  });

  it("treats empty strings as unset", () => {
    expect(getServerEnv({ BACKEND_URL: "  " }).BACKEND_URL).toBe(DEFAULT_BACKEND_URL);
  });

  it("accepts custom URLs and strips trailing slashes", () => {
    expect(getServerEnv({ BACKEND_URL: "http://backend:8000/" }).BACKEND_URL).toBe(
      "http://backend:8000",
    );
    expect(
      getPublicEnv({ NEXT_PUBLIC_API_URL: "https://api.example.org" }).NEXT_PUBLIC_API_URL,
    ).toBe("https://api.example.org");
  });

  it("rejects invalid URLs", () => {
    expect(() => getServerEnv({ BACKEND_URL: "not a url" })).toThrow(/Invalid server environment/);
    expect(() => getPublicEnv({ NEXT_PUBLIC_API_URL: "ftp://x.org" })).toThrow(
      /Invalid public environment/,
    );
  });
});
