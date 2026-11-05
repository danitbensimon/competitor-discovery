import { defineCollection, z } from 'astro:content';

const blog = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),              // the buyer's exact question
    answer: z.string(),
    teaser: z.string().optional(),  // 1 short line for the blog index card             // 2-3 sentence direct answer, shown first
    description: z.string(),        // meta description
    date: z.coerce.date(),
    lists: z.array(z.string()).default([]), // competitor slugs to link to
    faqs: z.array(z.object({ q: z.string(), a: z.string() })).default([]),
    art: z.object({ type: z.enum(['constellation', 'sources', 'spy']), data: z.array(z.object({ label: z.string(), n: z.number() })).optional() }).optional(), // hero art; defaults by post
    tag: z.string().default('Playbook'),   // post type shown on the blog index card
    draft: z.boolean().default(true),
  }),
});

export const collections = { blog };
