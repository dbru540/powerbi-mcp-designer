from powerbi_mcp.analysis.bindings import find_report_objects_by_model_reference
from powerbi_mcp.model.read import model_list_measures


def find_unused_measures(project_path: str) -> dict:
    measures_result = model_list_measures(project_path)
    if "error" in measures_result:
        return measures_result

    unused = []
    for measure in measures_result["measures"]:
        matches = find_report_objects_by_model_reference(
            project_path,
            measure["table"],
            measure["name"],
        )
        if "error" in matches:
            return matches
        if matches["count"] == 0:
            unused.append(measure)

    return {
        "unused_measures": unused,
        "count": len(unused),
    }


def impact_of_model_reference(project_path: str, entity: str, property_name: str) -> dict:
    matches = find_report_objects_by_model_reference(project_path, entity, property_name)
    if "error" in matches:
        return matches

    affected_pages = sorted({match["page_name"] for match in matches["matches"]})
    affected_visuals = [
        {
            "page_id": match["page_id"],
            "page_name": match["page_name"],
            "visual_id": match["visual_id"],
            "visual_type": match["visual_type"],
            "title": match["title"],
        }
        for match in matches["matches"]
    ]

    return {
        "entity": entity,
        "property_name": property_name,
        "affected_page_count": len(affected_pages),
        "affected_visual_count": matches["count"],
        "affected_pages": affected_pages,
        "affected_visuals": affected_visuals,
    }
