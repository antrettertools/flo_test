// plotly.js-dist-min ships no type declarations of its own, and
// @types/plotly.js only declares the 'plotly.js' module specifier. This
// project intentionally depends on the trimmed 'plotly.js-dist-min' runtime
// bundle instead of the full 'plotly.js' package (see
// frontend/src/components/TechnologyChart.tsx), so we declare the module
// here and reuse the already-installed @types/plotly.js types rather than
// falling back to `any`.
declare module 'plotly.js-dist-min' {
  const Plotly: typeof import('plotly.js');
  export default Plotly;
}
