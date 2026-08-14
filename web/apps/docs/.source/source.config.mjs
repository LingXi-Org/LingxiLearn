// source.config.ts
import { defineConfig, defineDocs, frontmatterSchema } from "fumadocs-mdx/config";
var docs = defineDocs({
  dir: "content/docs",
  docs: {
    schema: frontmatterSchema,
    postprocess: {
      includeProcessedMarkdown: true
    }
  }
});
var source_config_default = defineConfig();
export {
  source_config_default as default,
  docs
};
