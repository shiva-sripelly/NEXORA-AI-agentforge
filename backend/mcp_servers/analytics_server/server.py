from statistics import mean, median

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("AgentForge Analytics")


@mcp.tool()
def calculate_statistics(numbers: list[float]) -> dict:
    """Calculate count, sum, mean, minimum, maximum, and median for numbers."""
    if not numbers:
        raise ValueError("numbers must contain at least one value")
    if len(numbers) > 10_000:
        raise ValueError("numbers may contain at most 10000 values")
    return {
        "count": len(numbers), "sum": sum(numbers), "mean": mean(numbers),
        "min": min(numbers), "max": max(numbers), "median": median(numbers),
    }


@mcp.tool()
def analyze_text(text: str) -> dict:
    """Return safe counts describing a text value."""
    if len(text) > 100_000:
        raise ValueError("text may contain at most 100000 characters")
    words = text.split()
    return {
        "character_count": len(text), "word_count": len(words),
        "line_count": len(text.splitlines()) or 1,
        "unique_word_count": len({word.casefold() for word in words}),
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
