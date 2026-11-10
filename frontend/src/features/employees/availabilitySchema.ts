import { z } from "zod";

export const availabilitySchema = z
  .object({
    start_date: z.string().min(1, "Choose a start date"),
    end_date: z.string().min(1, "Choose an end date"),
    kind: z.enum(["leave", "comp_off", "unavailable"]),
    note: z.string().max(255).optional(),
  })
  .refine((values) => values.end_date >= values.start_date, {
    path: ["end_date"],
    message: "End date must be on or after the start date",
  })
  .refine(
    (values) =>
      (new Date(values.end_date).getTime() - new Date(values.start_date).getTime()) / 86_400_000 <=
      366,
    { path: ["end_date"], message: "Ranges cannot exceed 366 days" },
  );

export type AvailabilityForm = z.infer<typeof availabilitySchema>;
