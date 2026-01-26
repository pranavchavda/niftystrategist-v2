/**
 * AudioPlayer - Audio player component
 *
 * Props:
 * - url/src: URL of the audio file
 * - description/title: description or title of the audio
 * - autoplay: whether to autoplay (default: false)
 * - controls: show controls (default: true)
 * - loop: loop audio (default: false)
 */

export function AudioPlayer({
  url,
  src,
  description,
  title,
  autoplay = false,
  controls = true,
  loop = false,
  id,
  style,
}) {
  const audioSrc = url || src;
  const label = description || title;

  if (!audioSrc) {
    return (
      <div className="p-4 bg-zinc-100 dark:bg-zinc-800 rounded-md text-zinc-500">
        No audio URL provided
      </div>
    );
  }

  return (
    <div id={id} style={style} className="flex flex-col gap-2">
      {label && (
        <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
          {label}
        </span>
      )}
      <audio
        src={audioSrc}
        autoPlay={autoplay}
        controls={controls}
        loop={loop}
        className="w-full"
      >
        Your browser does not support the audio element.
      </audio>
    </div>
  );
}
