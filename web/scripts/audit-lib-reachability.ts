import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";

const root = process.cwd();
const libRoot = path.join(root, "lib");
type Ownership = Record<
	string,
	{
		owner: string;
		capability: string;
		status: "owned" | "compatibility";
		deletionCondition?: string;
	}
>;
const ownership = JSON.parse(
	readFileSync(path.join(libRoot, "ownership.json"), "utf8"),
) as Ownership;
const sourceExtensions = [".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"];
const importPattern =
	/(?:import|export)\s+(?:type\s+)?(?:[^'";]*?\s+from\s+)?['"]([^'"]+)['"]|import\(\s*(?:\/\*[\s\S]*?\*\/\s*)?['"]([^'"]+)['"]\s*\)|require(?:\.resolve)?\(\s*['"]([^'"]+)['"]\s*\)/g;
const dynamicImportPattern = /\bimport\(([\s\S]*?)\)/g;

function filesUnder(directory: string): string[] {
	if (!existsSync(directory)) return [];
	let entries: ReturnType<typeof readdirSync>;
	try {
		entries = readdirSync(directory, { withFileTypes: true });
	} catch {
		return [];
	}
	return entries.flatMap((entry) => {
		if (
			entry.isDirectory() &&
			["node_modules", ".next", ".pytest_cache", ".git", "coverage"].includes(
				entry.name,
			)
		)
			return [];
		const target = path.join(directory, entry.name);
		return entry.isDirectory() ? filesUnder(target) : [target];
	});
}

function isSource(file: string): boolean {
	return sourceExtensions.includes(path.extname(file));
}

function isTest(file: string): boolean {
	return /(?:^|[\\/])(?:__tests__|tests?)(?:[\\/]|$)|\.(?:test|spec)\.[^.]+$/.test(
		file,
	);
}

function resolveSource(base: string): string | undefined {
	const candidates = [
		base,
		...sourceExtensions.map((extension) => `${base}${extension}`),
		...sourceExtensions.map((extension) =>
			path.join(base, `index${extension}`),
		),
	];
	return candidates.find(
		(candidate) => existsSync(candidate) && statSync(candidate).isFile(),
	);
}

function resolveImport(from: string, specifier: string): string | undefined {
	if (specifier.startsWith("@/"))
		return resolveSource(path.join(root, specifier.slice(2)));
	if (specifier.startsWith("."))
		return resolveSource(path.resolve(path.dirname(from), specifier));
	return undefined;
}

function importsOf(file: string): string[] {
	const source = readFileSync(file, "utf8");
	const imports: string[] = [];
	for (const match of source.matchAll(importPattern)) {
		const resolved = resolveImport(file, match[1] ?? match[2] ?? match[3]);
		if (resolved) imports.push(resolved);
	}
	return imports;
}

function reachableFrom(entries: string[]): Set<string> {
	const reached = new Set<string>();
	const pending = [...entries];
	while (pending.length > 0) {
		const file = pending.pop();
		if (!file || reached.has(file)) continue;
		reached.add(file);
		for (const imported of importsOf(file)) pending.push(imported);
	}
	return reached;
}

const nextEntryPattern =
	/(?:^|[\\/])(?:page|layout|route|default|error|global-error|loading|not-found|unauthorized|forbidden|template|opengraph-image|twitter-image|sitemap|robots|manifest|icon)\.(?:ts|tsx|js|jsx)$/;
const rootEntries = [
	"bootstrap.ts",
	"drizzle.config.ts",
	"instrumentation.ts",
	"instrumentation-client.ts",
	"instrumentation-edge.ts",
	"instrumentation-node.ts",
	"next.config.ts",
	"proxy.ts",
	"telemetry.config.ts",
	"trigger.config.ts",
	"lib/execution/isolated-vm-worker.cjs",
	"lib/execution/sandbox/bundles/pptxgenjs.cjs",
	"lib/execution/sandbox/bundles/docx.cjs",
	"lib/execution/sandbox/bundles/pdf-lib.cjs",
]
	.map((entry) => path.join(root, entry))
	.filter(existsSync);
const productionEntries = [
	...filesUnder(path.join(root, "app")).filter((file) =>
		nextEntryPattern.test(file),
	),
	...filesUnder(path.join(root, "background")).filter(isSource),
	...rootEntries,
].filter((file) => !isTest(file));
const operationalEntries = [
	...filesUnder(path.join(root, "scripts")),
	...filesUnder(path.join(root, "lib", "db", "scripts")),
	path.join(root, "lib", "db", "drizzle.config.ts"),
].filter((file) => existsSync(file) && isSource(file) && !isTest(file));
const testEntries = filesUnder(root).filter(
	(file) =>
		isSource(file) &&
		isTest(file) &&
		!file.includes(`${path.sep}node_modules${path.sep}`),
);
const configuredGeneratedFiles = new Set(
	[
		"lib/api/contracts/generated/contracts.ts",
		"lib/api/contracts/generated/index.ts",
		"lib/api/contracts/generated/schemas.ts",
	].map((file) => path.join(root, file)),
);
const production = reachableFrom(productionEntries);
const operational = reachableFrom(operationalEntries);
const tests = reachableFrom(testEntries);
const allowedDynamicImports = new Map([
	[
		"bootstrap.ts:import(standaloneServer)",
		"Standalone server artifact path is selected from the build environment.",
	],
	[
		"lib/pptx-renderer/utils/pdf-renderer.ts:import(pdfjsUrl)",
		"PDF.js worker module is loaded from its configured external URL.",
	],
]);
const unresolvedDynamicImports = [...production].flatMap((file) => {
	const source = readFileSync(file, "utf8");
	return [...source.matchAll(dynamicImportPattern)].flatMap((match) => {
		const argument = match[1].trim().replace(/^(?:\/\*[\s\S]*?\*\/\s*)+/, "");
		if (argument.length === 0) return [];
		if (argument.startsWith("'") || argument.startsWith('"')) return [];
		const relativeFile = path.relative(root, file).replaceAll("\\", "/");
		const key = `${relativeFile}:${match[0].replace(/\s+/g, " ")}`;
		return [
			{
				file: relativeFile,
				expression: match[0],
				reason: allowedDynamicImports.get(key),
			},
		];
	});
});
const unknownDynamicImports = unresolvedDynamicImports.filter(
	(entry) => !entry.reason,
);
if (unknownDynamicImports.length > 0) {
	throw new Error(
		`Unreviewed non-literal dynamic imports: ${unknownDynamicImports
			.map((entry) => `${entry.file}:${entry.expression}`)
			.join(", ")}`,
	);
}

const inventory = readdirSync(libRoot, { withFileTypes: true })
	.filter((entry) => entry.isDirectory())
	.map((entry) => {
		const files = filesUnder(path.join(libRoot, entry.name)).filter(isSource);
		const productionFiles = files.filter((file) => production.has(file)).length;
		const operationalFiles = files.filter((file) =>
			operational.has(file),
		).length;
		const testFiles = files.filter((file) => tests.has(file)).length;
		const operationalOnlyFiles = files.filter(
			(file) =>
				!production.has(file) && !tests.has(file) && operational.has(file),
		);
		const generatedFiles = files.filter((file) =>
			configuredGeneratedFiles.has(file),
		);
		const testOnlyFiles = files.filter(
			(file) =>
				!production.has(file) &&
				tests.has(file) &&
				!operational.has(file) &&
				!configuredGeneratedFiles.has(file),
		);
		const testOnlyImplementationFiles = testOnlyFiles.filter(
			(file) => !isTest(file),
		);
		const unreachableFiles = files.filter(
			(file) =>
				!production.has(file) &&
				!tests.has(file) &&
				!operational.has(file) &&
				!configuredGeneratedFiles.has(file),
		);
		return {
			directory: entry.name,
			ownership: ownership[entry.name],
			sourceFiles: files.length,
			productionFiles,
			operationalFiles,
			testFiles,
			testOnlyFiles: testOnlyFiles.length,
			testOnlyFilePaths: testOnlyFiles.map((file) =>
				path.relative(root, file).replaceAll("\\", "/"),
			),
			testOnlyImplementationFiles: testOnlyImplementationFiles.length,
			testOnlyImplementationFilePaths: testOnlyImplementationFiles.map((file) =>
				path.relative(root, file).replaceAll("\\", "/"),
			),
			operationalOnlyFiles: operationalOnlyFiles.length,
			generatedFiles: generatedFiles.length,
			unreachableFiles: unreachableFiles.length,
			unreachableFilePaths: unreachableFiles.map((file) =>
				path.relative(root, file).replaceAll("\\", "/"),
			),
			sampleProductionFiles: files
				.filter((file) => production.has(file))
				.slice(0, 5)
				.map((file) => path.relative(root, file).replaceAll("\\", "/")),
			sampleUnreachableFiles: unreachableFiles
				.slice(0, 5)
				.map((file) => path.relative(root, file).replaceAll("\\", "/")),
			classification:
				productionFiles > 0
					? "production-reachable"
					: testFiles > 0
						? "test-only"
						: "unreachable",
		};
	})
	.filter((entry) => entry.sourceFiles > 0)
	.sort((left, right) => left.directory.localeCompare(right.directory));

function directoriesUnder(directory: string): string[] {
	return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
		if (!entry.isDirectory()) return [];
		const target = path.join(directory, entry.name);
		return [target, ...directoriesUnder(target)];
	});
}

const testOnlyDirectories = new Set(
	directoriesUnder(libRoot).filter((directory) => {
		const files = filesUnder(directory).filter(isSource);
		return (
			files.length > 0 &&
			files.every(
				(file) =>
					!production.has(file) &&
					!operational.has(file) &&
					!configuredGeneratedFiles.has(file),
			)
		);
	}),
);
const maximalTestOnlySubtrees = [...testOnlyDirectories]
	.filter((directory) => !testOnlyDirectories.has(path.dirname(directory)))
	.map((directory) => path.relative(root, directory).replaceAll("\\", "/"))
	.sort();
const testOnlyImplementationAbsolutePaths = new Set(
	inventory.flatMap((entry) =>
		entry.testOnlyImplementationFilePaths.map((file) => path.join(root, file)),
	),
);
const reverseTestImports = new Map<string, Set<string>>();
for (const file of tests) {
	for (const imported of importsOf(file)) {
		const importers = reverseTestImports.get(imported) ?? new Set<string>();
		importers.add(file);
		reverseTestImports.set(imported, importers);
	}
}
const testOnlyDependents = new Set(testOnlyImplementationAbsolutePaths);
const pendingTestOnlyDependents = [...testOnlyImplementationAbsolutePaths];
while (pendingTestOnlyDependents.length > 0) {
	const file = pendingTestOnlyDependents.pop();
	if (!file) continue;
	for (const importer of reverseTestImports.get(file) ?? []) {
		if (testOnlyDependents.has(importer)) continue;
		testOnlyDependents.add(importer);
		pendingTestOnlyDependents.push(importer);
	}
}
const testEntriesDependingOnTestOnlyImplementation = testEntries
	.filter((file) => testOnlyDependents.has(file))
	.map((file) => path.relative(root, file).replaceAll("\\", "/"))
	.sort();

const inventoryDirectories = new Set(inventory.map((entry) => entry.directory));
const missingOwnership = inventory
	.filter((entry) => !entry.ownership)
	.map((entry) => entry.directory);
const staleOwnership = Object.keys(ownership).filter(
	(directory) => !inventoryDirectories.has(directory),
);
const unreachableSourceFiles = inventory.flatMap(
	(entry) => entry.unreachableFilePaths,
);
const testOnlyImplementationSourceFiles = inventory.flatMap(
	(entry) => entry.testOnlyImplementationFilePaths,
);
const compatibilityWithoutDeletionCondition = Object.entries(ownership)
	.filter(
		([, entry]) =>
			entry.status === "compatibility" && !entry.deletionCondition?.trim(),
	)
	.map(([directory]) => directory);
if (
	missingOwnership.length > 0 ||
	staleOwnership.length > 0 ||
	compatibilityWithoutDeletionCondition.length > 0
) {
	throw new Error(
		`web/lib ownership mismatch: missing=[${missingOwnership.join(",")}], stale=[${staleOwnership.join(",")}], compatibilityWithoutDeletionCondition=[${compatibilityWithoutDeletionCondition.join(",")}]`,
	);
}
if (unreachableSourceFiles.length > 0) {
	throw new Error(
		`Unowned web/lib source files are not reachable from production, operational, tests, or configured generators: ${unreachableSourceFiles.join(", ")}`,
	);
}
if (testOnlyImplementationSourceFiles.length > 0) {
	throw new Error(
		`Production-shaped web/lib source may not be retained solely by tests: ${testOnlyImplementationSourceFiles.join(", ")}`,
	);
}

process.stdout.write(
	`${JSON.stringify(
		{
			productionEntrypoints: productionEntries.map((file) =>
				path.relative(root, file).replaceAll("\\", "/"),
			),
			operationalEntrypoints: operationalEntries.map((file) =>
				path.relative(root, file).replaceAll("\\", "/"),
			),
			unresolvedDynamicImports,
			maximalTestOnlySubtrees,
			testEntriesDependingOnTestOnlyImplementation,
			inventory,
		},
		null,
		2,
	)}\n`,
);
