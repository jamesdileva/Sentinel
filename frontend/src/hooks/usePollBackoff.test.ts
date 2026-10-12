import { describe, expect, it } from "vitest";

import { FIRST_POLL_MS, MAX_POLL_MS, nextPollDelay } from "./usePollBackoff";

describe("nextPollDelay", () => {
  it("starts at 2 s so short jobs still resolve fast", () => {
    expect(nextPollDelay(0)).toBe(FIRST_POLL_MS);
    expect(nextPollDelay(1999)).toBe(FIRST_POLL_MS);
  });

  it("doubles as the wait gets longer", () => {
    expect(nextPollDelay(2000)).toBe(4000);
    expect(nextPollDelay(4000)).toBe(8000);
  });

  it("caps at 10 s", () => {
    expect(nextPollDelay(60_000)).toBe(MAX_POLL_MS);
    expect(nextPollDelay(600_000)).toBe(MAX_POLL_MS);
  });

  it("stays positive for any elapsed time", () => {
    for (const elapsed of [0, 1, 1999, 2000, 9999, 599_999]) {
      expect(nextPollDelay(elapsed)).toBeGreaterThan(0);
      expect(nextPollDelay(elapsed)).toBeLessThanOrEqual(MAX_POLL_MS);
    }
  });
});
