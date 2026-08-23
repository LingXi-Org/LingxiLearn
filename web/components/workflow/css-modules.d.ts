/**
 * Ambient declaration for CSS Modules used by renderer dependencies.
 * (which imports CSS modules) as part of its program, so it needs this in scope
 * for a standalone type-check. Consuming apps (Next.js) provide their own.
 */
declare module "*.module.css" {
	const classes: { readonly [key: string]: string };
	export default classes;
}

declare module "*.css";
