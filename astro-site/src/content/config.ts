import { defineCollection, z } from 'astro:content';

const blog = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),              // the buyer's exact question
    answer: z.string(),             // 2-3 sentence direct answer, shown first
    description: z.string(),        // meta description
    date: z.coerce.date(),
    lists: z.array(z.string()).default([]), // competitor slugs to link to
    faqs: z.array(z.object({ q: z.string(), a: z.string() })).default([]),
    tag: z.string().default('Playbook'),   // post type shown on the blog index card
    draft: z.boolean().default(true),
  }),
});

export const collections = { blog };
