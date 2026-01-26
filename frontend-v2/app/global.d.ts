import type { FunctionComponent, SVGAttributes } from 'react';

declare module '*.png' {
  const value: string;
  export default value;
}

declare module '*.webp' {
  const value: string;
  export default value;
}

declare module '*.jpg' {
  const value: string;
  export default value;
}

declare module '*.jpeg' {
  const value: string;
  export default value;
}

declare module '*.svg' {
  const content: FunctionComponent<SVGAttributes<SVGElement>>;
  export default content;
}

declare global {
  interface ImportMeta {
    env?: {
      DEV?: boolean;
      [key: string]: unknown;
    };
  }
}