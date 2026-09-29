import { HOME_FAQ } from "@/lib/home-faq";
import { pageMetadata } from "@/lib/seo";

import {
  FaqJsonLd,
  OrganizationJsonLd,
  WebsiteJsonLd,
  SoftwareApplicationJsonLd,
} from "@/components/marketing/json-ld";
import { AppleEditAxis } from "@/components/prototypes/redesign/apple-edit-axis";

export const metadata = pageMetadata("/");

export default function HomePage() {
  return (
    <>
      <OrganizationJsonLd />
      <WebsiteJsonLd />
      <SoftwareApplicationJsonLd />
      <FaqJsonLd
        items={HOME_FAQ.map(({ question, answer }) => ({
          q: question,
          a: answer,
        }))}
      />
      <AppleEditAxis />
    </>
  );
}
