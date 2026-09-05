"use client";

import { Container } from "@/components/ui/container";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

export function Faq({ items }: { items: { q: string; a: string }[] }) {
  return (
    <section className="relative border-b border-white/[0.06] py-24 md:py-32">
      <Container>
        <div className="grid gap-12 lg:grid-cols-12 lg:gap-16">
          <div className="lg:col-span-4">
            <span className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#4da3ff]">
              FAQ
            </span>
            <h2 className="mt-4 text-[clamp(1.9rem,3.2vw,2.6rem)] font-semibold leading-[1.05] tracking-[-0.03em] text-white">
              Straight answers
            </h2>
          </div>

          <div className="lg:col-span-8">
            <Accordion type="single" collapsible className="w-full">
              {items.map((item, i) => (
                <AccordionItem
                  key={item.q}
                  value={`item-${i}`}
                  className="border-b border-white/[0.07]"
                >
                  <AccordionTrigger className="py-5 text-left text-[16.5px] font-medium text-white hover:no-underline">
                    {item.q}
                  </AccordionTrigger>
                  <AccordionContent className="pb-6 text-[15px] leading-relaxed text-white/50">
                    {item.a}
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          </div>
        </div>
      </Container>
    </section>
  );
}
