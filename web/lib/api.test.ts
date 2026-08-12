import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";

describe("artifact API", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("does not prepend /api twice for same-origin artifact URLs", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("artifact", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const url = api.agentArtifactUrl("t-123", "visual");

    await api.fetchArtifact(url);

    expect(fetchMock).toHaveBeenCalledWith(url, expect.any(Object));
    expect(url).not.toContain("/api/api/");
  });
});
