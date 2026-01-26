/**
 * Image - Image display
 *
 * Props:
 * - src: URL of the image
 * - alt: alt text
 * - width: optional width in pixels
 * - height: optional height in pixels
 * - maxWidth: optional max width (default: 100%)
 * - aspectRatio: optional aspect ratio (e.g., '16/9', '1/1', '4/3')
 */

export function Image({ src, alt = '', width, height, maxWidth, aspectRatio, id, style: propStyle }) {
  const style = { ...propStyle };

  if (width) style.width = typeof width === 'number' ? `${width}px` : width;
  if (height) style.height = typeof height === 'number' ? `${height}px` : height;
  if (maxWidth) style.maxWidth = typeof maxWidth === 'number' ? `${maxWidth}px` : maxWidth;
  if (aspectRatio) style.aspectRatio = aspectRatio;

  return (
    <img
      id={id}
      src={src}
      alt={alt}
      style={style}
      className="rounded-md object-cover max-w-full h-auto"
      loading="lazy"
    />
  );
}
