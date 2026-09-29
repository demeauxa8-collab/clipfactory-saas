"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, Menu } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import styles from "./mobile-menu.module.css";

export function MobileMenu() {
  const [open, setOpen] = useState(false);
  const followingLink = useRef(false);
  function follow() { followingLink.current = true; setOpen(false); }
  return (
    <div className={styles.mobileOnly}>
      <Dialog open={open} onOpenChange={(value) => { followingLink.current = false; setOpen(value); }}>
        <DialogTrigger asChild><button type="button" className={styles.trigger} aria-label="Open navigation menu"><Menu aria-hidden="true" /></button></DialogTrigger>
        <DialogContent className={styles.panel} onCloseAutoFocus={(event) => { if (followingLink.current) event.preventDefault(); }}>
          <DialogTitle>ClipFactory</DialogTitle>
          <DialogDescription>Your next cut starts here.</DialogDescription>
          <nav aria-label="Mobile navigation" className={styles.links}>
            <Link href="/#story" onClick={follow}>How it works <ArrowUpRight aria-hidden="true" /></Link>
            <Link href="/#campaign-v6" onClick={follow}>Features <ArrowUpRight aria-hidden="true" /></Link>
            <Link href="/pricing" onClick={follow}>Pricing <ArrowUpRight aria-hidden="true" /></Link>
            <Link href="/login" onClick={follow}>Sign in <ArrowUpRight aria-hidden="true" /></Link>
          </nav>
          <Link href="/app/campaigns/new" onClick={follow} className={styles.cta}>Start a campaign <ArrowUpRight aria-hidden="true" /></Link>
        </DialogContent>
      </Dialog>
    </div>
  );
}
