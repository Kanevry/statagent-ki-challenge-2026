import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import UseCases from "./UseCases";

afterEach(cleanup);

describe("UseCases", () => {
  it("zeigt den gemeinsamen Einstieg offen mit Link auf /uc4", () => {
    const { container } = render(<UseCases />);
    expect(container.querySelector('a[href="/uc4"]')).not.toBeNull();
    expect(container.querySelector("details")).toBeNull();
  });

  it("führt alle drei Use Cases auf", () => {
    const { container } = render(<UseCases />);
    for (const route of ["/uc1", "/uc2", "/uc3"]) {
      expect(container.querySelector(`a[href="${route}"]`), route).not.toBeNull();
    }
  });
});
