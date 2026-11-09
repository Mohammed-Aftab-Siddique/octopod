import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ErrorBanner } from "@/components/ErrorBanner";

describe("ErrorBanner", () => {
  it("announces its message", () => {
    render(<ErrorBanner message="Something failed" />);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Something failed");
  });

  it("renders nothing without a message", () => {
    const { container } = render(<ErrorBanner message={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});
