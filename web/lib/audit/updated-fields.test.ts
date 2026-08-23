import { describe, expect, it } from "vitest";
import { auditMock } from "@/tests/support";
import { auditUpdatedFields } from "./updated-fields";

describe("auditUpdatedFields", () => {
	it("returns the written columns", () => {
		expect(
			auditUpdatedFields({ name: "Renamed", url: "https://example.com" }),
		).toEqual(["name", "url"]);
	});

	it("drops updatedAt, which every write moves", () => {
		expect(
			auditUpdatedFields({ name: "Renamed", updatedAt: new Date() }),
		).toEqual(["name"]);
	});

	it("keeps columns explicitly written as null — clearing a value is a change", () => {
		expect(
			auditUpdatedFields({ lastConnected: null, lastError: null }),
		).toEqual(["lastConnected", "lastError"]);
	});

	it("returns an empty list when only updatedAt was written", () => {
		expect(auditUpdatedFields({ updatedAt: new Date() })).toEqual([]);
	});

	/**
	 * `auditMock` carries its own copy because the testing package cannot import
	 * application code without creating a dependency cycle. The copy is pinned
	 * from this side, where the dependency already runs in the safe direction.
	 */
	it("stays in step with the copy @/tests/support hands to mocked callers", () => {
		const cases: object[] = [
			{ name: "Renamed", url: "https://example.com" },
			{ name: "Renamed", updatedAt: new Date() },
			{ lastConnected: null, lastError: null },
			{ updatedAt: new Date() },
			{},
		];
		for (const updateValues of cases) {
			expect(auditMock.auditUpdatedFields(updateValues)).toEqual(
				auditUpdatedFields(updateValues),
			);
		}
	});
});
