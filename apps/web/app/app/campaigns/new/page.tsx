import { ProductPageIntro } from "@/components/product/product-primitives";
import { NewCampaignForm } from "./new-campaign-form";
import styles from "./new-campaign.module.css";

export const metadata = { title: "New campaign" };

export default function NewCampaignPage() {
  return (
    <div className={`cf-page cf-page--narrow ${styles.page}`}>
      <ProductPageIntro
        eyebrow="New campaign · 3 chapters"
        title="Build the campaign lens."
        description="Define the promise, audience and boundaries once. ClipFactory uses this brief to judge every source and explain why each moment belongs."
        className={styles.intro}
      />
      <NewCampaignForm />
    </div>
  );
}
