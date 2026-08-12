import Image from "next/image";

const logoAssets = {
  mark: {
    src: "/images/brand/airis-mark.png",
    width: 909,
    height: 885,
  },
  wordmark: {
    src: "/images/brand/airis-wordmark.png",
    width: 720,
    height: 442,
  },
};

export function Logo({
  className = "",
  withMark = true,
}: {
  className?: string;
  withMark?: boolean;
}) {
  return (
    <span className={`inline-flex items-center gap-2.5 overflow-hidden rounded-sm bg-white px-1.5 py-0.5 leading-none ${className}`}>
      {withMark && (
        <Image
          src={logoAssets.mark.src}
          width={logoAssets.mark.width}
          height={logoAssets.mark.height}
          alt=""
          aria-hidden
          className="block h-full w-auto shrink-0"
          decoding="async"
          draggable={false}
          unoptimized
        />
      )}
      <Image
        src={logoAssets.wordmark.src}
        width={logoAssets.wordmark.width}
        height={logoAssets.wordmark.height}
        alt="Airis Residence"
        className="block h-full w-auto shrink-0"
        decoding="async"
        draggable={false}
        unoptimized
      />
    </span>
  );
}
