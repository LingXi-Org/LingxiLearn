module.exports = {
  forbidden: [
    {
      name: 'shared-is-leaf',
      from: { path: '^shared/' },
      to: { path: '^(entities|features|app)/' },
    },
    {
      name: 'entities-only-depend-on-shared',
      from: { path: '^entities/' },
      to: { path: '^(features|app)/' },
    },
    {
      name: 'features-do-not-depend-on-app',
      from: { path: '^features/' },
      to: { path: '^app/' },
    },
    {
      name: 'no-cycles',
      severity: 'error',
      from: {},
      to: { circular: true },
    }
  ],
  options: {
    tsConfig: { fileName: 'tsconfig.production.json' },
    doNotFollow: { path: 'node_modules' },
    exclude: { path: '(^|/)node_modules/' },
  },
}
