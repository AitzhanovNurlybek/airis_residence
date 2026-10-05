import { redirect } from "next/navigation";

import { ReviewsBoard } from "@/components/admin/ReviewsBoard";
import { adminFetch, isAdminSignedIn } from "@/lib/adminServer";
import type { AdminReview } from "@/lib/adminTypes";

export default async function AdminReviewsPage() {
  const [signedIn, res] = await Promise.all([isAdminSignedIn(), adminFetch("/api/admin/reviews")]);
  if (!signedIn) redirect("/admin/login");
  const reviews: AdminReview[] = res.ok ? await res.json() : [];
  return <ReviewsBoard initialReviews={reviews} />;
}
