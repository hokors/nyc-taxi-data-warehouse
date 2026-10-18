import type { ReactNode, ButtonHTMLAttributes } from "react";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`card ${className}`}>{children}</section>;
}

export function Button({
  children,
  variant = "secondary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" }) {
  return <button className={`button ${variant} ${className}`} {...props}>{children}</button>;
}

export function Badge({ children, tone = "green" }: { children: ReactNode; tone?: "green" | "neutral" | "amber" }) {
  return <span className={`badge ${tone === "neutral" ? "neutral" : tone === "amber" ? "amber" : ""}`}>{children}</span>;
}

export function SelectField({
  label, value, options, onChange, wide = false,
}: {
  label: string; value: string; options: readonly string[]; onChange: (value: string) => void; wide?: boolean;
}) {
  return (
    <label className={`select-field ${wide ? "wide" : ""}`}>
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => <option key={option} value={option}>{option}</option>)}
      </select>
    </label>
  );
}
