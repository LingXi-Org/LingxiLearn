#!/usr/bin/env bun
/**
 * Deterministic TypeScript / Zod contract generator.
 *
 * Reads the OpenAPI JSON produced by ``scripts/export_openapi.py`` and emits
 * Zod schemas + route contracts under ``web/lib/api/contracts/generated/``.
 *
 * The output is byte-deterministic: identical input always produces identical
 * output, so the generated directory can be committed and CI can diff it.
 *
 * Usage:
 *   bun run web/scripts/generate-rest-contracts.ts            # write
 *   bun run web/scripts/generate-rest-contracts.ts --check     # exit 1 if stale
 */

import { readFileSync, writeFileSync, existsSync } from "fs";
import { join, dirname, resolve } from "path";
import { fileURLToPath } from "url";

// ---------------------------------------------------------------------------
// Paths
// ---------------------------------------------------------------------------

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const REPO_ROOT = resolve(__dirname, "../..");
const OPENAPI_PATH = join(REPO_ROOT, "var/openapi/rest-contracts.json");
const OUT_DIR = join(REPO_ROOT, "web/lib/api/contracts/generated");

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------

const isCheck = process.argv.includes("--check");

// ---------------------------------------------------------------------------
// OpenAPI → Zod conversion
// ---------------------------------------------------------------------------

type OpenAPISchema = Record<string, unknown>;

/** Convert a PascalCase name to a valid TS identifier for a Zod schema. */
function schemaVarName(name: string): string {
  return `${name}Schema`;
}

/** Convert an operationId to a camelCase contract variable name. */
function contractVarName(operationId: string): string {
  const camel = operationId.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
  return `${camel}Contract`;
}

/** Convert OpenAPI path `{param}` to Next.js `[param]`. */
function toNextPath(oapiPath: string): string {
  return oapiPath.replace(/\{([^}]+)\}/g, "[$1]");
}

/** Render a JS literal as a TS expression string (for default values). */
function renderLiteral(value: unknown): string {
  if (value === null) return "null";
  if (value === undefined) return "undefined";
  if (typeof value === "string") return JSON.stringify(value);
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) return `[${value.map(renderLiteral).join(", ")}]`;
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>)
      .map(([k, v]) => `${JSON.stringify(k)}: ${renderLiteral(v)}`)
      .join(", ");
    return `{ ${entries} }`;
  }
  return String(value);
}

/**
 * Convert an OpenAPI schema fragment to a Zod expression string.
 *
 * @param schema   The OpenAPI schema (or sub-schema) to convert.
 * @param required Whether this field is in the parent's `required` array.
 */
function toZod(schema: OpenAPISchema, required = true): string {
  const expr = toZodInner(schema);
  // Apply default if present
  if ("default" in schema && schema.default !== undefined) {
    return `${expr}.default(${renderLiteral(schema.default)})`;
  }
  return expr;
}

function toZodInner(schema: OpenAPISchema): string {
  // $ref
  if (schema.$ref) {
    const refName = (schema.$ref as string).split("/").pop()!;
    return schemaVarName(refName);
  }

  // anyOf — typically [type, null] for nullable
  if (schema.anyOf) {
    const variants = schema.anyOf as OpenAPISchema[];
    const nonNull = variants.filter((v) => v.type !== "null");
    const hasNull = variants.some((v) => v.type === "null");

    if (nonNull.length === 1 && hasNull) {
      // Simple nullable: z.string().nullable()
      return `${toZodInner(nonNull[0])}.nullable()`;
    }
    if (nonNull.length > 1) {
      // Union type
      const unionParts = nonNull.map(toZodInner);
      if (hasNull) {
        return `z.union([${unionParts.join(", ")}]).nullable()`;
      }
      return `z.union([${unionParts.join(", ")}])`;
    }
    // Fallback
    return "z.unknown()";
  }

  const type = schema.type as string | undefined;

  if (type === "string") {
    let expr = "z.string()";
    if (typeof schema.minLength === "number") expr += `.min(${schema.minLength})`;
    if (typeof schema.maxLength === "number") expr += `.max(${schema.maxLength})`;
    return expr;
  }

  if (type === "integer" || type === "number") {
    let expr = "z.number()";
    if (type === "integer") expr += ".int()";
    if (typeof schema.minimum === "number") expr += `.min(${schema.minimum})`;
    if (typeof schema.maximum === "number") expr += `.max(${schema.maximum})`;
    return expr;
  }

  if (type === "boolean") {
    return "z.boolean()";
  }

  if (type === "array") {
    const items = schema.items as OpenAPISchema | undefined;
    if (!items) return "z.array(z.unknown())";
    let expr = `z.array(${toZodInner(items)})`;
    if (typeof schema.minItems === "number") expr += `.min(${schema.minItems})`;
    if (typeof schema.maxItems === "number") expr += `.max(${schema.maxItems})`;
    return expr;
  }

  if (type === "object") {
    const props = schema.properties as Record<string, OpenAPISchema> | undefined;
    const additionalProps = schema.additionalProperties;

    if (!props || Object.keys(props).length === 0) {
      // Free-form object
      if (additionalProps === true || (typeof additionalProps === "object" && additionalProps !== null)) {
        return "z.record(z.string(), z.unknown())";
      }
      return "z.object({}).passthrough()";
    }

    // Object with known properties
    const required = (schema.required as string[]) || [];
    const entries = Object.entries(props)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([key, propSchema]) => {
        const isReq = required.includes(key);
        const zodExpr = toZod(propSchema, isReq);
        const safeKey = /^[a-zA-Z_$][a-zA-Z0-9_$]*$/.test(key) ? key : JSON.stringify(key);
        return `  ${safeKey}: ${zodExpr},`;
      });

    let expr = `z.object({\n${entries.join("\n")}\n})`;
    if (additionalProps === true) {
      expr += ".catchall(z.unknown())";
    }
    return expr;
  }

  // No type — could be a bare schema with only $ref or other markers
  if (!type) {
    return "z.unknown()";
  }

  return "z.unknown()";
}

// ---------------------------------------------------------------------------
// Topological sort for schemas (dependency order)
// ---------------------------------------------------------------------------

/** Collect all $ref targets from an OpenAPI schema fragment. */
function collectRefs(schema: OpenAPISchema): Set<string> {
  const refs = new Set<string>();
  function walk(obj: unknown) {
    if (Array.isArray(obj)) {
      for (const item of obj) walk(item);
    } else if (obj && typeof obj === "object") {
      const rec = obj as Record<string, unknown>;
      if (typeof rec.$ref === "string") {
        refs.add(rec.$ref.split("/").pop()!);
      }
      for (const v of Object.values(rec)) walk(v);
    }
  }
  walk(schema);
  return refs;
}

/** Topological sort: dependencies before dependents, alphabetical within each level. */
function topoSortSchemas(schemas: Record<string, OpenAPISchema>): string[] {
  const allNames = new Set(Object.keys(schemas));
  const deps = new Map<string, Set<string>>();

  for (const [name, schema] of Object.entries(schemas)) {
    const refs = collectRefs(schema);
    // Only keep refs to schemas that exist in our set, exclude self
    const selfRefs = new Set([...refs].filter((r) => allNames.has(r) && r !== name));
    deps.set(name, selfRefs);
  }

  const result: string[] = [];
  const visited = new Set<string>();

  function visit(name: string, stack: Set<string>) {
    if (visited.has(name)) return;
    if (stack.has(name)) return; // cycle — break
    stack.add(name);
    for (const dep of deps.get(name) || []) {
      visit(dep, stack);
    }
    stack.delete(name);
    visited.add(name);
    result.push(name);
  }

  // Visit in alphabetical order for determinism
  for (const name of [...allNames].sort()) {
    visit(name, new Set());
  }

  return result;
}

// ---------------------------------------------------------------------------
// Schema generation
// ---------------------------------------------------------------------------

function generateSchemasFile(schemas: Record<string, OpenAPISchema>): string {
  const lines: string[] = [];
  lines.push(`// AUTO-GENERATED — do not edit by hand.`);
  lines.push(`// Regenerate:  python scripts/export_openapi.py && bun run web/scripts/generate-rest-contracts.ts`);
  lines.push(`// eslint-disable @typescript-eslint/no-explicit-any`);
  lines.push(``);
  lines.push(`import { z } from "zod";`);
  lines.push(``);

  const sortedNames = topoSortSchemas(schemas);

  for (const name of sortedNames) {
    const s = schemas[name];
    const isSelfRecursive = collectRefs(s).has(name);
    if (s.type !== "object" || !s.properties) {
      // Non-object top-level schema (rare)
      const schemaExpr = toZod(s);
      lines.push(
        isSelfRecursive
          ? `export const ${schemaVarName(name)}: z.ZodType<any> = z.lazy(() => ${schemaExpr});`
          : `export const ${schemaVarName(name)} = ${schemaExpr};`,
      );
    } else {
      const required = (s.required as string[]) || [];
      const props = s.properties as Record<string, OpenAPISchema>;
      const additionalProps = s.additionalProperties;

      const entries = Object.entries(props)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([key, propSchema]) => {
          const isReq = required.includes(key);
          const zodExpr = toZod(propSchema, isReq);
          const safeKey = /^[a-zA-Z_$][a-zA-Z0-9_$]*$/.test(key) ? key : JSON.stringify(key);
          return `  ${safeKey}: ${zodExpr},`;
        });

      let objExpr = `z.object({\n${entries.join("\n")}\n})`;
      if (additionalProps === true) {
        objExpr += ".catchall(z.unknown())";
      }

      if (s.description) {
        lines.push(`/** ${(s.description as string).replace(/\*\//g, "* /")} */`);
      }
      lines.push(
        isSelfRecursive
          ? `export const ${schemaVarName(name)}: z.ZodType<any> = z.lazy(() => ${objExpr});`
          : `export const ${schemaVarName(name)} = ${objExpr};`,
      );
    }

    lines.push(`export type ${name} = z.output<typeof ${schemaVarName(name)}>;`);
    lines.push(``);
  }

  return lines.join("\n");
}

// ---------------------------------------------------------------------------
// Contract generation
// ---------------------------------------------------------------------------

interface PathItem {
  [method: string]: {
    operationId?: string;
    parameters?: Array<{
      in: string;
      name: string;
      required?: boolean;
      schema: OpenAPISchema;
    }>;
    responses?: Record<string, {
      content?: Record<string, { schema: OpenAPISchema }>;
      description?: string;
    }>;
    summary?: string;
  };
}

const HTTP_METHODS = ["get", "post", "put", "patch", "delete"] as const;

function generateContractsFile(
  paths: Record<string, PathItem>,
  schemas: Record<string, OpenAPISchema>,
): string {
  const lines: string[] = [];
  lines.push(`// AUTO-GENERATED — do not edit by hand.`);
  lines.push(`// Regenerate:  python scripts/export_openapi.py && bun run web/scripts/generate-rest-contracts.ts`);
  lines.push(`// eslint-disable @typescript-eslint/no-explicit-any`);
  lines.push(``);
  lines.push(`import { z } from "zod";`);
  lines.push(`import { defineRouteContract } from "@/lib/api/contracts/types";`);
  lines.push(`import * as S from "./schemas";`);
  lines.push(``);

  const sortedPaths = Object.keys(paths).sort();
  const generatedContracts: string[] = [];

  for (const pathKey of sortedPaths) {
    const pathItem = paths[pathKey];
    const nextPath = toNextPath(pathKey);

    for (const method of HTTP_METHODS) {
      const op = pathItem[method];
      if (!op) continue;

      const operationId = op.operationId || `${method}_${pathKey.replace(/[^a-zA-Z0-9]/g, "_")}`;
      const response200 = op.responses?.["200"];
      const jsonContent = response200?.content?.["application/json"];
      const responseSchemaRef = jsonContent?.schema;

      // Only generate contracts for endpoints with a $ref response (response_model bound)
      if (!responseSchemaRef?.$ref) continue;

      const refName = (responseSchemaRef.$ref as string).split("/").pop()!;
      const varName = contractVarName(operationId);
      const httpMethod = method.toUpperCase();

      // Collect path params
      const pathParams = (op.parameters || []).filter((p) => p.in === "path");
      // Collect query params
      const queryParams = (op.parameters || []).filter((p) => p.in === "query");

      const contractParts: string[] = [];
      contractParts.push(`  method: "${httpMethod}" as const,`);
      contractParts.push(`  path: "${nextPath}",`);

      // Path params schema
      if (pathParams.length > 0) {
        const paramEntries = pathParams
          .sort((a, b) => a.name.localeCompare(b.name))
          .map((p) => `    ${p.name}: z.string(),`)
          .join("\n");
        contractParts.push(`  params: z.object({\n${paramEntries}\n  }),`);
      }

      // Query params schema
      if (queryParams.length > 0) {
        const queryEntries = queryParams
          .sort((a, b) => a.name.localeCompare(b.name))
          .map((p) => {
            const zodType = toZod(p.schema, p.required === true);
            return `    ${p.name}: ${zodType},`;
          })
          .join("\n");
        contractParts.push(`  query: z.object({\n${queryEntries}\n  }),`);
      }

      contractParts.push(`  response: {`);
      contractParts.push(`    mode: "json" as const,`);
      contractParts.push(`    schema: S.${schemaVarName(refName)},`);
      contractParts.push(`  },`);

      lines.push(`export const ${varName} = defineRouteContract({`);
      lines.push(contractParts.join("\n"));
      lines.push(`});`);
      lines.push(``);

      generatedContracts.push(varName);
    }
  }

  // Summary comment
  lines.unshift(
    `// ${generatedContracts.length} contracts generated from ${sortedPaths.length} paths.`,
  );

  return lines.join("\n");
}

// ---------------------------------------------------------------------------
// Index barrel
// ---------------------------------------------------------------------------

function generateIndexFile(): string {
  return [
    `// AUTO-GENERATED — do not edit by hand.`,
    `// Re-exports all generated schemas and contracts.`,
    ``,
    `export * from "./schemas";`,
    `export * from "./contracts";`,
    ``,
  ].join("\n");
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

function main(): void {
  const raw = readFileSync(OPENAPI_PATH, "utf-8");
  const spec = JSON.parse(raw);

  const schemas = (spec.components?.schemas ?? {}) as Record<string, OpenAPISchema>;
  const paths = (spec.paths ?? {}) as Record<string, PathItem>;

  const schemasContent = generateSchemasFile(schemas);
  const contractsContent = generateContractsFile(paths, schemas);
  const indexContent = generateIndexFile();

  const schemasPath = join(OUT_DIR, "schemas.ts");
  const contractsPath = join(OUT_DIR, "contracts.ts");
  const indexPath = join(OUT_DIR, "index.ts");

  if (isCheck) {
    let ok = true;
    for (const [target, content] of [
      [schemasPath, schemasContent],
      [contractsPath, contractsContent],
      [indexPath, indexContent],
    ] as const) {
      if (!existsSync(target)) {
        console.error(`MISSING  ${target}`);
        ok = false;
        continue;
      }
      const existing = readFileSync(target, "utf-8");
      if (existing !== content) {
        console.error(`STALE    ${target}  — re-run: bun run web/scripts/generate-rest-contracts.ts`);
        ok = false;
      }
    }
    if (ok) {
      const schemaCount = Object.keys(schemas).length;
      console.log(`OK       ${schemaCount} schemas, contracts up to date`);
    } else {
      process.exit(1);
    }
    return;
  }

  // Write mode
  for (const [target, content] of [
    [schemasPath, schemasContent],
    [contractsPath, contractsContent],
    [indexPath, indexContent],
  ] as const) {
    writeFileSync(target, content, "utf-8");
  }

  const schemaCount = Object.keys(schemas).length;
  const contractCount = (contractsContent.match(/defineRouteContract/g) || []).length;
  console.log(`WROTE    ${schemaCount} schemas, ${contractCount} contracts → ${OUT_DIR}`);
}

main();
