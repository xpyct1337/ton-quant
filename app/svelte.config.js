import adapter from '@sveltejs/adapter-static';
const base = process.env.BASE_PATH ?? '/ton-quant';
export default {
  kit: {
    adapter: adapter({ fallback: '404.html' }),
    paths: { base, relative: false },
    prerender: {
      // vanilla pages are copied into the publish dir by the deploy workflow,
      // so they don't exist at build time — don't fail the crawl on them.
      handleHttpError: ({ path }) => { if (path.endsWith('.html')) return; throw new Error('prerender: ' + path); }
    }
  }
};
