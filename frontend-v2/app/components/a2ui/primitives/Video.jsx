/**
 * Video - Video player component
 *
 * Props:
 * - url/src: URL of the video
 * - autoplay: whether to autoplay (default: false)
 * - controls: show controls (default: true)
 * - loop: loop video (default: false)
 * - muted: mute video (default: false)
 * - poster: poster image URL
 */

export function Video({
  url,
  src,
  autoplay = false,
  controls = true,
  loop = false,
  muted = false,
  poster,
  id,
  style,
}) {
  const videoSrc = url || src;

  if (!videoSrc) {
    return (
      <div className="p-4 bg-zinc-100 dark:bg-zinc-800 rounded-md text-zinc-500">
        No video URL provided
      </div>
    );
  }

  return (
    <video
      id={id}
      src={videoSrc}
      autoPlay={autoplay}
      controls={controls}
      loop={loop}
      muted={muted}
      poster={poster}
      style={style}
      className="rounded-md max-w-full"
    >
      Your browser does not support the video tag.
    </video>
  );
}
