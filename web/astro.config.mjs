// @ts-check
import { defineConfig } from 'astro/config';
import react from '@astrojs/react';
import tailwindcss from '@tailwindcss/vite';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/** @type {import('astro').AstroUserConfig} */
export default defineConfig({
  integrations: [react()],
  site: process.env.SITE_URL || 'https://skill-store.pages.dev',
  base: '/',
  vite: {
    plugins: [tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
  },
  build: {
    assets: 'assets',
  },
});
