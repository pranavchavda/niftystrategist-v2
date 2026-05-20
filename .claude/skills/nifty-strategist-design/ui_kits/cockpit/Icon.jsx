// Tiny Lucide adapter — reads window.lucide.icons[PascalCaseName]
// (the same data the UMD's createIcons() uses) and renders it as
// real React SVG so it survives re-renders.
function Icon({ name, size = 16, strokeWidth = 2, className, style, color }) {
  const key = name.split('-').map(w => w[0].toUpperCase() + w.slice(1)).join('');
  const def = (typeof window !== 'undefined' && window.lucide && window.lucide.icons)
    ? window.lucide.icons[key]
    : null;
  if (!def) {
    return <span aria-hidden="true" style={{ display: 'inline-block', width: size, height: size, ...style }} className={className} />;
  }
  // Lucide UMD shape: def is directly an array of [tag, attrs] pairs.
  const children = Array.isArray(def) ? def : (def.children || []);
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={color || 'currentColor'}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      style={style}
      aria-hidden="true"
    >
      {children.map((c, i) => React.createElement(c[0], { key: i, ...c[1] }))}
    </svg>
  );
}

window.Icon = Icon;
