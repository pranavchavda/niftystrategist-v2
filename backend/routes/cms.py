"""
API routes for Content Management System (CMS).
Provides interface for editing Shopify metaobjects.
"""
import os
import json
import subprocess
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, HTTPException, Header, Query, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from routes.uploads import get_user_email_from_token

logger = logging.getLogger(__name__)

router = APIRouter()

# Path to bash-tools directory (relative to backend/)
IDC_TOOLS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "bash-tools")

# Thread pool executor for running subprocess commands asynchronously
# This prevents blocking the async event loop during long-running operations
executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="cms-subprocess")


class PageCreate(BaseModel):
    """Model for creating a new category landing page"""
    urlHandle: str  # Required
    title: str      # Required


class PageUpdate(BaseModel):
    """Model for category landing page updates"""
    # Hero section (optional - can update individually)
    heroTitle: Optional[str] = None
    heroDescription: Optional[str] = None
    # Basic fields
    urlHandle: Optional[str] = None
    title: Optional[str] = None
    # SEO fields
    seoTitle: Optional[str] = None
    seoDescription: Optional[str] = None
    # Settings
    enableSorting: Optional[bool] = None
    # Product references
    featuredProducts: Optional[List[str]] = None  # List of product GIDs
    # Sorting options (metaobject references)
    sortingOptions: Optional[List[str]] = None  # List of sorting_option metaobject GIDs
    # Categories (metaobject references)
    categories: Optional[List[str]] = None  # List of category_section metaobject GIDs
    # Educational content (metaobject references)
    educationalContent: Optional[List[str]] = None  # List of educational_block metaobject GIDs
    # Comparison table (SINGLE metaobject reference)
    comparisonTable: Optional[str] = None  # Single comparison_table metaobject GID
    # FAQ section (SINGLE metaobject reference)
    faqSection: Optional[str] = None  # Single faq_section metaobject GID


class HeroRegenerateRequest(BaseModel):
    """Model for hero image regeneration request"""
    template: str = "home_barista"  # Default template (used if hero text not provided)
    model: str = "gpt5-image-mini"  # Default to GPT-5-image-mini (can also use "gemini")
    heroTitle: Optional[str] = None  # For contextual prompting
    heroDescription: Optional[str] = None  # For contextual prompting
    customPrompt: Optional[str] = None  # Custom prompt (overrides template and contextual)


class MetaobjectCreate(BaseModel):
    """Model for creating a metaobject"""
    type: str  # Metaobject type (e.g., "category_section", "educational_block")
    fields: Dict[str, Any]  # Field key-value pairs
    createPlaceholder: bool = True  # For FAQ/comparison types: create placeholder items (default True for backward compat)


class MetaobjectUpdate(BaseModel):
    """Model for updating a metaobject"""
    type: str  # Metaobject type
    fields: Dict[str, Any]  # Field key-value pairs to update


class HomeBannerUpdate(BaseModel):
    """Model for updating home page banner"""
    heading: Optional[str] = None
    text: Optional[str] = None
    cta: Optional[str] = None
    link: Optional[str] = None
    imageId: Optional[str] = None  # MediaImage GID


class TextLinkCreate(BaseModel):
    """Model for creating a text_link metaobject"""
    link_text: str
    link_location: str
    image_id: Optional[str] = None  # MediaImage GID (optional)


class TextLinkUpdate(BaseModel):
    """Model for updating a text_link metaobject"""
    link_text: Optional[str] = None
    link_location: Optional[str] = None
    image_id: Optional[str] = None


class HeaderBannerUpdate(BaseModel):
    """Model for updating header_banner link reference"""
    text_link_id: str  # Text link metaobject GID to reference


def run_idc_command(command: List[str], cwd: str = IDC_TOOLS_PATH) -> Dict[str, Any]:
    """
    Run a command in the iDC tools directory and return parsed output.

    Args:
        command: Command to run as list of strings
        cwd: Working directory for command execution

    Returns:
        Parsed JSON output from command

    Raises:
        HTTPException if command fails
    """
    try:
        logger.info(f"Running command: {' '.join(command)}")

        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=120,  # 2 minute timeout
            env={**os.environ, "PYTHONUNBUFFERED": "1"}
        )

        if result.returncode != 0:
            logger.error(f"Command failed: {result.stderr}")
            raise HTTPException(
                status_code=500,
                detail=f"Command failed: {result.stderr or result.stdout}"
            )

        # Try to parse JSON output
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            # If not JSON, return as text
            return {"output": result.stdout}

    except subprocess.TimeoutExpired:
        logger.error("Command timed out")
        raise HTTPException(status_code=504, detail="Command timed out")
    except Exception as e:
        logger.error(f"Command execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def run_idc_command_async(
    command: List[str],
    cwd: str = IDC_TOOLS_PATH,
    timeout: int = 300
) -> Dict[str, Any]:
    """
    Run a command asynchronously in the bash-tools directory and return parsed output.

    This prevents blocking the FastAPI event loop during long-running operations like
    hero image regeneration or complex metaobject operations.

    Args:
        command: Command to run as list of strings
        cwd: Working directory for command execution
        timeout: Timeout in seconds (default 300s = 5 minutes, up from 120s)

    Returns:
        Parsed JSON output from command

    Raises:
        HTTPException if command fails
    """
    loop = asyncio.get_event_loop()

    def _run_subprocess():
        """Internal function to run subprocess in thread pool."""
        try:
            logger.info(f"Running async command: {' '.join(command)}")

            result = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**os.environ, "PYTHONUNBUFFERED": "1"}
            )

            if result.returncode != 0:
                logger.error(f"Command failed: {result.stderr}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Command failed: {result.stderr or result.stdout}"
                )

            # Try to parse JSON output
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                # If not JSON, return as text
                return {"output": result.stdout}

        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out after {timeout}s")
            raise HTTPException(
                status_code=504,
                detail=f"Command timed out after {timeout} seconds"
            )
        except Exception as e:
            logger.error(f"Command execution error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # Run subprocess in thread pool to avoid blocking event loop
    try:
        return await loop.run_in_executor(executor, _run_subprocess)
    except HTTPException:
        # Re-raise HTTPException as-is
        raise
    except Exception as e:
        logger.error(f"Executor error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/cms/category-landing-pages")
async def get_category_landing_pages(authorization: Optional[str] = Header(None)):
    """
    Get all category landing page metaobjects with hero section data.

    Returns list of category pages with their hero images, titles, and descriptions.
    """
    user_email = get_user_email_from_token(authorization)

    try:
        # Query for category_landing_page metaobjects
        # We'll use a Python script to query Shopify metaobjects
        # For now, let's create a simple query using GraphQL

        # Check if there's a script to list metaobjects
        # If not, we'll need to create one or use GraphQL directly

        command = [
            "python3",
            "cms/list_category_landing_pages.py"  # We'll need to create this
        ]

        result = await run_idc_command_async(command)

        # Transform the data for frontend
        pages = result.get("pages", [])

        return {"pages": pages}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching category pages: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/cms/category-landing-pages")
async def create_category_landing_page(
    create: PageCreate,
    authorization: Optional[str] = Header(None)
):
    """
    Create a new category landing page metaobject.

    Args:
        create: Page creation data (urlHandle and title required)

    Returns:
        Created page data
    """
    user_email = get_user_email_from_token(authorization)

    try:
        logger.info(f"Creating new category landing page for user {user_email}")
        logger.info(f"URL Handle: {create.urlHandle}, Title: {create.title}")

        # Create empty landing page with minimal required fields
        command = [
            "python3",
            "cms/create_empty_category_landing_page.py",
            "--url-handle", create.urlHandle,
            "--title", create.title,
        ]

        result = await run_idc_command_async(command, cwd=IDC_TOOLS_PATH)

        if result.get("success"):
            return result.get("page", {})
        else:
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Failed to create category landing page")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating category landing page: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/cms/category-landing-pages")
async def update_category_landing_page(
    update: PageUpdate,
    page_id: str = Query(..., description="Metaobject GID"),
    authorization: Optional[str] = Header(None)
):
    """
    Update category landing page fields.

    Args:
        page_id: Metaobject GID
        update: Page fields to update

    Returns:
        Updated page data
    """
    user_email = get_user_email_from_token(authorization)

    try:
        logger.info(f"Updating page {page_id} for user {user_email}")

        # Build command with only provided fields
        command = [
            "python3",
            "cms/update_category_landing_page.py",
            "--page-id", page_id,
        ]

        # Add optional fields if provided
        if update.heroTitle is not None:
            command.extend(["--hero-title", update.heroTitle])
        if update.heroDescription is not None:
            command.extend(["--hero-description", update.heroDescription])
        if update.urlHandle is not None:
            command.extend(["--url-handle", update.urlHandle])
        if update.title is not None:
            command.extend(["--title", update.title])
        if update.seoTitle is not None:
            command.extend(["--seo-title", update.seoTitle])
        if update.seoDescription is not None:
            command.extend(["--seo-description", update.seoDescription])
        if update.enableSorting is not None:
            command.extend(["--enable-sorting", "true" if update.enableSorting else "false"])
        if update.featuredProducts is not None:
            # Pass as JSON array
            command.extend(["--featured-products", json.dumps(update.featuredProducts)])
        if update.sortingOptions is not None:
            # Pass as JSON array
            command.extend(["--sorting-options", json.dumps(update.sortingOptions)])
        if update.categories is not None:
            # Pass as JSON array
            command.extend(["--categories", json.dumps(update.categories)])
        if update.educationalContent is not None:
            # Pass as JSON array
            command.extend(["--educational-content", json.dumps(update.educationalContent)])
        if update.comparisonTable is not None:
            # Pass as single GID string (no JSON encoding)
            command.extend(["--comparison-table", update.comparisonTable])
        if update.faqSection is not None:
            # Pass as single GID string (no JSON encoding)
            command.extend(["--faq-section", update.faqSection])

        result = await run_idc_command_async(command)

        return result.get("page", {})

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating category page: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/cms/category-landing-pages/regenerate-hero")
async def regenerate_hero_image(
    request: HeroRegenerateRequest,
    page_id: str = Query(..., description="Metaobject GID"),
    authorization: Optional[str] = Header(None)
):
    """
    Regenerate hero image using AI via OpenRouter.
    Supports GPT-5-image-mini (OpenAI) and Gemini 2.5 Flash Image (Google).

    Args:
        page_id: Metaobject GID
        request: Regeneration parameters (template name, optional model)

    Returns:
        Updated page data with new hero image
    """
    user_email = get_user_email_from_token(authorization)

    try:
        # Determine which model to use (default to GPT-5-image-mini)
        model = getattr(request, 'model', 'gpt5-image-mini')

        logger.info(f"Regenerating hero image for page {page_id}")
        logger.info(f"Template: {request.template}, Model: {model}")

        # Build command with optional hero text for contextual prompting
        command = [
            "python3",
            "cms/regenerate_hero_image.py",
            "--metaobject-id", page_id,
            "--template", request.template,
            "--model", model,
            "--output-format", "json"
        ]

        # Add custom prompt if provided (highest priority)
        if request.customPrompt:
            command.extend(["--custom-prompt", request.customPrompt])
            logger.info("Using custom prompt")
        # Otherwise add hero text for contextual prompting
        elif request.heroTitle and request.heroDescription:
            command.extend(["--hero-title", request.heroTitle])
            command.extend(["--hero-description", request.heroDescription])
            logger.info("Using contextual prompting from hero text")
        else:
            logger.info(f"Using template: {request.template}")

        result = await run_idc_command_async(command, cwd=IDC_TOOLS_PATH)

        if result.get("success"):
            return result.get("page", {})
        else:
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Failed to regenerate hero image")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error regenerating hero image: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/cms/category-landing-pages/upload-hero")
async def upload_hero_image(
    file: UploadFile = File(...),
    page_id: str = Query(..., description="Metaobject GID"),
    authorization: Optional[str] = Header(None)
):
    """
    Upload a custom hero image file.

    Args:
        file: Image file (JPEG, PNG, WebP)
        page_id: Metaobject GID

    Returns:
        Updated page data with new hero image
    """
    user_email = get_user_email_from_token(authorization)

    try:
        logger.info(f"Uploading hero image for page {page_id} (user: {user_email})")

        # Validate file type
        allowed_types = ["image/jpeg", "image/png", "image/webp"]
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed: {', '.join(allowed_types)}"
            )

        # Read file contents
        file_contents = await file.read()

        # Save to temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file.filename.split('.')[-1]}") as tmp:
            tmp.write(file_contents)
            tmp_path = tmp.name

        try:
            # Use upload_hero_image.py script
            command = [
                "python3",
                "cms/upload_hero_image.py",
                "--metaobject-id", page_id,
                "--image-path", tmp_path,
                "--output-format", "json"
            ]

            result = await run_idc_command_async(command, cwd=IDC_TOOLS_PATH)

            if result.get("success"):
                return result.get("page", {})
            else:
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", "Failed to upload hero image")
                )
        finally:
            # Clean up temp file
            os.unlink(tmp_path)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading hero image: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/cms/shopify-files")
async def list_shopify_files(
    authorization: Optional[str] = Header(None),
    file_type: str = Query("image", description="File type filter")
):
    """
    List files from Shopify Files (CDN).

    Args:
        file_type: Filter by file type (default: image)

    Returns:
        List of Shopify files with URLs
    """
    user_email = get_user_email_from_token(authorization)

    try:
        # Use list_shopify_files.py script
        command = [
            "python3",
            "cms/list_shopify_files.py",
            "--file-type", file_type
        ]

        result = await run_idc_command_async(command, cwd=IDC_TOOLS_PATH)

        return {"files": result.get("files", [])}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing Shopify files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/cms/category-landing-pages/set-hero-image")
async def set_hero_image_from_cdn(
    page_id: str = Query(..., description="Metaobject GID"),
    file_id: str = Query(..., description="Shopify File GID"),
    authorization: Optional[str] = Header(None)
):
    """
    Set hero image from an existing Shopify CDN file.

    Args:
        page_id: Metaobject GID
        file_id: Shopify File GID

    Returns:
        Updated page data
    """
    user_email = get_user_email_from_token(authorization)

    try:
        logger.info(f"Setting hero image for page {page_id} to file {file_id}")

        # Use set_hero_image.py script
        command = [
            "python3",
            "cms/set_hero_image.py",
            "--metaobject-id", page_id,
            "--file-id", file_id,
            "--output-format", "json"
        ]

        result = await run_idc_command_async(command, cwd=IDC_TOOLS_PATH)

        if result.get("success"):
            return result.get("page", {})
        else:
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Failed to set hero image")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting hero image: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/cms/products/search")
async def search_products(
    query: str = Query("", description="Search query (Shopify syntax)"),
    limit: int = Query(10, description="Max results to return"),
    authorization: Optional[str] = Header(None)
):
    """
    Search for products using Shopify search syntax.

    Args:
        query: Search query (e.g., "tag:sale", "vendor:DeLonghi", "price:>100")
        limit: Maximum number of results to return

    Returns:
        List of products with basic info (id, title, handle, vendor, price)
    """
    user_email = get_user_email_from_token(authorization)

    try:
        # Use search_products.py script
        command = [
            "python3",
            "products/search_products.py",
            query if query else "status:active",  # Default to active products
            "--limit", str(limit),
            "--fields", "id", "title", "handle", "vendor", "price"
        ]

        result = await run_idc_command_async(command, cwd=IDC_TOOLS_PATH)

        # Result is a list of products
        if isinstance(result, list):
            products = result
        else:
            products = []

        return {"products": products}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching products: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/cms/metaobjects/categories")
async def list_category_section_metaobjects(
    authorization: Optional[str] = Header(None)
):
    """
    List all category_section metaobjects.

    Returns list of metaobjects with id, title, description, collection_handle.
    """
    user_email = get_user_email_from_token(authorization)

    try:
        command = [
            "python3",
            "cms/list_metaobjects.py",
            "--type", "category_section",
            "--output-format", "json"
        ]

        result = await run_idc_command_async(command, cwd=IDC_TOOLS_PATH)

        return {"metaobjects": result.get("metaobjects", [])}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing category_section metaobjects: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/cms/metaobjects/educational-blocks")
async def list_educational_block_metaobjects(
    authorization: Optional[str] = Header(None)
):
    """
    List all educational_block metaobjects.

    Returns list of metaobjects with id, title, content_type, image.
    """
    user_email = get_user_email_from_token(authorization)

    try:
        command = [
            "python3",
            "cms/list_metaobjects.py",
            "--type", "educational_block",
            "--output-format", "json"
        ]

        result = await run_idc_command_async(command, cwd=IDC_TOOLS_PATH)

        return {"metaobjects": result.get("metaobjects", [])}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing educational_block metaobjects: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/cms/metaobjects/faq-sections")
async def list_faq_section_metaobjects(
    authorization: Optional[str] = Header(None)
):
    """
    List all faq_section metaobjects.

    Returns list of metaobjects with id, title, question_count.
    """
    user_email = get_user_email_from_token(authorization)

    try:
        command = [
            "python3",
            "cms/list_metaobjects.py",
            "--type", "faq_section",
            "--output-format", "json"
        ]

        result = await run_idc_command_async(command, cwd=IDC_TOOLS_PATH)

        return {"metaobjects": result.get("metaobjects", [])}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing faq_section metaobjects: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/cms/metaobjects/comparison-tables")
async def list_comparison_table_metaobjects(
    authorization: Optional[str] = Header(None)
):
    """
    List all comparison_table metaobjects.

    Returns list of metaobjects with id, title, product_count, feature_count.
    """
    user_email = get_user_email_from_token(authorization)

    try:
        command = [
            "python3",
            "cms/list_metaobjects.py",
            "--type", "comparison_table",
            "--output-format", "json"
        ]

        result = await run_idc_command_async(command, cwd=IDC_TOOLS_PATH)

        return {"metaobjects": result.get("metaobjects", [])}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing comparison_table metaobjects: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/cms/metaobjects/sorting-options")
async def list_sorting_option_metaobjects(
    authorization: Optional[str] = Header(None)
):
    """
    List all sorting_option metaobjects.

    Returns list of metaobjects with id, label, type, value, icon, color.
    These are used for configuring the Sorting Pills component on category pages.
    """
    user_email = get_user_email_from_token(authorization)

    try:
        command = [
            "python3",
            "cms/list_metaobjects.py",
            "--type", "sorting_option",
            "--output-format", "json"
        ]

        result = await run_idc_command_async(command, cwd=IDC_TOOLS_PATH)

        return {"metaobjects": result.get("metaobjects", [])}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing sorting_option metaobjects: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# GENERIC METAOBJECT CRUD ENDPOINTS
# ============================================================================


@router.post("/api/cms/metaobjects/create")
async def create_metaobject(
    create: MetaobjectCreate,
    authorization: Optional[str] = Header(None)
):
    """
    Create a new metaobject of any type.

    Args:
        create: Metaobject type and fields

    Returns:
        Created metaobject data

    Example body:
        {
            "type": "category_section",
            "fields": {
                "title": "Best Espresso Machines",
                "description": "...",
                "collection_handle": "espresso-machines"
            }
        }
    """
    user_email = get_user_email_from_token(authorization)

    try:
        logger.info(f"Creating metaobject of type '{create.type}' for user {user_email}")

        # Special handling for FAQ sections and comparison tables
        # These require nested items to satisfy Shopify validation (questions/features are REQUIRED fields)
        if create.type in ['faq_section', 'comparison_table'] and create.createPlaceholder:
            # Step 1: Create placeholder item FIRST (only if createPlaceholder=True)
            logger.info(f"createPlaceholder={create.createPlaceholder} - creating placeholder items")
            if create.type == 'faq_section':
                logger.info(f"Creating placeholder FAQ item (step 1/2)")
                # Create rich text JSON for answer
                answer_json = json.dumps({
                    "type": "root",
                    "children": [{"type": "paragraph", "children": [{"type": "text", "value": "Click edit to add your answer"}]}]
                })

                item_command = [
                    "python3",
                    "cms/create_metaobject.py",
                    "--type", "faq_item",
                    "--question", "Add your first question",
                    "--answer", answer_json,
                    "--priority", "1",
                    "--output-format", "json"
                ]

                item_result = await run_idc_command_async(item_command, cwd=IDC_TOOLS_PATH)
                if not item_result.get("success"):
                    error_msg = item_result.get("error", "Failed to create placeholder FAQ item")
                    logger.error(f"Placeholder item creation failed: {error_msg}")
                    raise HTTPException(status_code=500, detail=error_msg)

                item_data = item_result.get("metaobject", {})
                item_id = item_data.get('id')
                logger.info(f"Successfully created placeholder FAQ item: {item_id}")
                reference_ids = [item_id]
                reference_field = "questions"

            elif create.type == 'comparison_table':
                logger.info(f"Creating placeholder comparison feature (step 1/2)")
                feature_command = [
                    "python3",
                    "cms/create_metaobject.py",
                    "--type", "comparison_feature",
                    "--name", "Add your first feature",
                    "--description", "Click edit to add feature description",
                    "--output-format", "json"
                ]

                feature_result = await run_idc_command_async(feature_command, cwd=IDC_TOOLS_PATH)
                if not feature_result.get("success"):
                    error_msg = feature_result.get("error", "Failed to create placeholder feature")
                    logger.error(f"Placeholder feature creation failed: {error_msg}")
                    raise HTTPException(status_code=500, detail=error_msg)

                feature_data = feature_result.get("metaobject", {})
                feature_id = feature_data.get('id')
                logger.info(f"Successfully created placeholder feature: {feature_id}")
                reference_ids = [feature_id]
                reference_field = "features"

            # Step 2: Create the section/table WITH the placeholder item/feature reference
            logger.info(f"Creating {create.type} with placeholder items (step 2/2)")

            command = [
                "python3",
                "cms/create_metaobject.py",
                "--type", create.type,
            ]

            # Add all fields from the request
            for field_key, field_value in create.fields.items():
                cli_key = field_key.replace('_', '-')
                command.extend([f"--{cli_key}", str(field_value)])

            # Add the reference field with the placeholder items
            command.extend([f"--{reference_field}", json.dumps(reference_ids)])
            command.extend(["--output-format", "json"])

            logger.info(f"Running command: {' '.join(command)}")
            result = await run_idc_command_async(command, cwd=IDC_TOOLS_PATH)

            if not result.get("success"):
                error_msg = result.get("error", "Failed to create metaobject")
                logger.error(f"Create metaobject failed: {error_msg}")
                raise HTTPException(status_code=500, detail=error_msg)

            section_data = result.get("metaobject", {})
            logger.info(f"Successfully created {create.type} with placeholder items")

            # Return metaobject data with placeholder IDs for frontend badge display
            return {
                **section_data,
                "placeholderIds": reference_ids,  # Frontend can show "Incomplete" badge
                "placeholderCreated": True
            }

        else:
            # Standard creation for other types OR when createPlaceholder=False
            # If createPlaceholder=False for FAQ/comparison types, frontend MUST provide
            # reference IDs in fields (e.g., fields.questions = ["gid://..."])
            command = [
                "python3",
                "cms/create_metaobject.py",
                "--type", create.type,
            ]

            # Add each field as a separate argument
            for field_key, field_value in create.fields.items():
                # Convert field name from camelCase or snake_case to kebab-case for CLI
                cli_key = field_key.replace('_', '-')
                command.extend([f"--{cli_key}", str(field_value)])

            command.extend(["--output-format", "json"])

            result = await run_idc_command_async(command, cwd=IDC_TOOLS_PATH)

            if result.get("success"):
                logger.info(f"Successfully created metaobject: {result.get('metaobject', {}).get('id')}")
                return result.get("metaobject", {})
            else:
                error_msg = result.get("error", "Failed to create metaobject")
                logger.error(f"Create metaobject failed: {error_msg}")
                raise HTTPException(status_code=500, detail=error_msg)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating metaobject: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/cms/metaobjects")
async def update_metaobject(
    update: MetaobjectUpdate,
    id: str = Query(...),
    authorization: Optional[str] = Header(None)
):
    """
    Update an existing metaobject.

    Args:
        id: Metaobject GID (as query parameter)
        update: Metaobject type and fields to update (in body)

    Returns:
        Updated metaobject data

    Example:
        PUT /api/cms/metaobjects?id=gid://shopify/Metaobject/123
        Body: {
            "type": "category_section",
            "fields": {
                "title": "Updated Title",
                "description": "Updated description"
            }
        }
    """
    user_email = get_user_email_from_token(authorization)

    try:
        logger.info(f"Updating metaobject {id} for user {user_email}")
        logger.info(f"Update data: type={update.type}, fields={update.fields}")

        # Build command with ID, type, and individual field arguments
        command = [
            "python3",
            "cms/update_metaobject.py",
            "--id", id,
            "--type", update.type,
        ]

        # Add each field as a separate argument
        for field_key, field_value in update.fields.items():
            # Convert field name from camelCase or snake_case to kebab-case for CLI
            cli_key = field_key.replace('_', '-')
            command.extend([f"--{cli_key}", str(field_value)])

        command.extend(["--output-format", "json"])

        logger.info(f"Running command: {' '.join(command)}")

        result = await run_idc_command_async(command, cwd=IDC_TOOLS_PATH)

        if result.get("success"):
            logger.info(f"Successfully updated metaobject: {id}")
            return result.get("metaobject", {})
        else:
            error_msg = result.get("error", "Failed to update metaobject")
            logger.error(f"Update metaobject failed: {error_msg}")
            raise HTTPException(status_code=500, detail=error_msg)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating metaobject: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/cms/metaobjects")
async def delete_metaobject(
    id: str = Query(...),
    type: str = Query(..., description="Metaobject type"),
    authorization: Optional[str] = Header(None)
):
    """
    Delete a metaobject.

    Args:
        id: Metaobject GID (as query parameter)
        type: Metaobject type (e.g., "category_section") (as query parameter)

    Returns:
        Success status

    Example:
        DELETE /api/cms/metaobjects?id=gid://shopify/Metaobject/123&type=category_section
    """
    user_email = get_user_email_from_token(authorization)

    try:
        logger.info(f"Deleting metaobject {id} (type: {type}) for user {user_email}")

        # Build command with ID (type parameter not needed for delete)
        command = [
            "python3",
            "cms/delete_metaobject.py",
            "--id", id,
            "--confirm",
            "--output-format", "json"
        ]

        result = await run_idc_command_async(command, cwd=IDC_TOOLS_PATH)

        if result.get("success"):
            logger.info(f"Successfully deleted metaobject: {id}")
            return {"success": True, "message": "Metaobject deleted successfully"}
        else:
            error_msg = result.get("error", "Failed to delete metaobject")
            logger.error(f"Delete metaobject failed: {error_msg}")
            raise HTTPException(status_code=500, detail=error_msg)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting metaobject: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/cms/metaobjects/full")
async def get_metaobject_full(
    id: str = Query(...),
    authorization: Optional[str] = Header(None)
):
    """
    Get full details of a metaobject with nested items expanded.

    This endpoint resolves nested metaobject references and includes full item data.
    For example, an faq_section will include all faq_item details within it.

    Args:
        id: Metaobject GID (as query parameter)

    Returns:
        Complete metaobject data with all nested items expanded

    Example:
        GET /api/cms/metaobjects/full?id=gid://shopify/Metaobject/123
    """
    user_email = get_user_email_from_token(authorization)

    try:
        logger.info(f"Fetching full metaobject {id} for user {user_email}")

        # Build command with ID to get full details
        command = [
            "python3",
            "cms/get_metaobject.py",
            "--id", id,
            "--include-nested",  # Flag to include nested items
            "--output-format", "json"
        ]

        result = await run_idc_command_async(command, cwd=IDC_TOOLS_PATH)

        if result.get("success"):
            logger.info(f"Successfully fetched full metaobject: {id}")
            return result.get("metaobject", {})
        else:
            error_msg = result.get("error", "Failed to fetch metaobject")
            logger.error(f"Get full metaobject failed: {error_msg}")
            raise HTTPException(status_code=404, detail=error_msg)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching full metaobject: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/cms/metaobjects/{metaobject_id}")
async def get_metaobject(
    metaobject_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Get full details of a metaobject by ID.

    Args:
        metaobject_id: Metaobject GID

    Returns:
        Complete metaobject data with all fields

    Example:
        GET /api/cms/metaobjects/gid://shopify/Metaobject/123
    """
    user_email = get_user_email_from_token(authorization)

    try:
        logger.info(f"Fetching metaobject {metaobject_id} for user {user_email}")

        # Build command with ID
        command = [
            "python3",
            "cms/get_metaobject.py",
            "--id", metaobject_id,
            "--output-format", "json"
        ]

        result = await run_idc_command_async(command, cwd=IDC_TOOLS_PATH)

        if result.get("success"):
            logger.info(f"Successfully fetched metaobject: {metaobject_id}")
            return result.get("metaobject", {})
        else:
            error_msg = result.get("error", "Failed to fetch metaobject")
            logger.error(f"Get metaobject failed: {error_msg}")
            raise HTTPException(status_code=404, detail=error_msg)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching metaobject: {e}")
        raise HTTPException(status_code=500, detail=str(e))
"""
Banner-specific API endpoints to be appended to cms.py
These handle home page banners and header top banner management.
"""

# ============================================================================
# HOME PAGE BANNERS ENDPOINTS
# ============================================================================

@router.get("/api/cms/home-banners")
async def list_home_banners(
    market: Optional[str] = Query(None, regex="^(ca|us)$"),
    authorization: Optional[str] = Header(None)
):
    """
    List all homepage main banners.

    Query Parameters:
        market: Filter by market ('ca' or 'us')

    Returns:
        List of banner objects with id, handle, market, type, heading, text, cta, link, image info

    Example:
        GET /api/cms/home-banners
        GET /api/cms/home-banners?market=ca
    """
    user_email = get_user_email_from_token(authorization)

    try:
        logger.info(f"Listing home banners for user {user_email}, market filter: {market}")

        command = [
            "python3",
            "cms/list_home_banners.py",
            "--format", "json"
        ]

        if market:
            command.extend(["--market", market])

        result = await run_idc_command_async(command, cwd=IDC_TOOLS_PATH)

        # Result is an array of banners
        logger.info(f"Successfully fetched {len(result)} banners")
        return {"banners": result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing home banners: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/cms/home-banners/{identifier}")
async def get_home_banner(
    identifier: str,
    authorization: Optional[str] = Header(None)
):
    """
    Get a single home banner by handle or ID.

    Args:
        identifier: Banner handle (e.g., "primary-banner") or GID

    Returns:
        Complete banner data with nested structure

    Example:
        GET /api/cms/home-banners/primary-banner
        GET /api/cms/home-banners/gid://shopify/Metaobject/12714018
    """
    user_email = get_user_email_from_token(authorization)

    try:
        logger.info(f"Fetching home banner {identifier} for user {user_email}")

        command = [
            "python3",
            "cms/get_home_banner.py",
            identifier,
            "--format", "json"
        ]

        result = await run_idc_command_async(command, cwd=IDC_TOOLS_PATH)

        logger.info(f"Successfully fetched banner: {identifier}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching home banner: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/cms/home-banners/{identifier}")
async def update_home_banner(
    identifier: str,
    update_data: HomeBannerUpdate,
    authorization: Optional[str] = Header(None)
):
    """
    Update a home banner's fields.

    Args:
        identifier: Banner handle or GID
        update_data: Fields to update (heading, text, cta, link, imageId)

    Returns:
        Updated banner data

    Example:
        PUT /api/cms/home-banners/primary-banner
        {
            "heading": "New Sale",
            "text": "Up to 50% off",
            "cta": "Shop Now"
        }
    """
    user_email = get_user_email_from_token(authorization)

    try:
        logger.info(f"Updating home banner {identifier} for user {user_email}")

        command = [
            "python3",
            "cms/update_home_banner.py",
            identifier,
            "--format", "json"
        ]

        # Add fields to update
        if update_data.heading is not None:
            command.extend(["--heading", update_data.heading])
        if update_data.text is not None:
            command.extend(["--text", update_data.text])
        if update_data.cta is not None:
            command.extend(["--cta", update_data.cta])
        if update_data.link is not None:
            command.extend(["--link", update_data.link])
        if update_data.imageId is not None:
            command.extend(["--image-id", update_data.imageId])

        result = await run_idc_command_async(command, cwd=IDC_TOOLS_PATH)

        logger.info(f"Successfully updated banner: {identifier}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating home banner: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# HEADER BANNER ENDPOINTS
# ============================================================================

@router.get("/api/cms/header-banner")
async def get_header_banner(
    authorization: Optional[str] = Header(None)
):
    """
    Get the header banner with all 6 text_link references.

    Returns:
        Header banner data with nested text_link data for CA and US markets

    Example:
        GET /api/cms/header-banner
        Returns: {
            "id": "gid://...",
            "handle": "header-banner",
            "links": {
                "ca": { "left": {...}, "center": {...}, "right": {...} },
                "us": { "left": {...}, "center": {...}, "right": {...} }
            }
        }
    """
    user_email = get_user_email_from_token(authorization)

    try:
        logger.info(f"Fetching header banner for user {user_email}")

        command = [
            "python3",
            "cms/get_header_banner.py",
            "--format", "json"
        ]

        result = await run_idc_command_async(command, cwd=IDC_TOOLS_PATH)

        logger.info("Successfully fetched header banner")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching header banner: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/cms/header-banner/{position}")
async def update_header_banner_position(
    position: str,
    update_data: HeaderBannerUpdate,
    authorization: Optional[str] = Header(None)
):
    """
    Update which text_link is shown in a specific header position.

    Args:
        position: Link position (left_link, centre_link, right_link, us_left_link, us_center_link, us_right_link)
        update_data: text_link_id to reference

    Returns:
        Updated header banner data

    Example:
        PUT /api/cms/header-banner/centre_link
        { "text_link_id": "gid://shopify/Metaobject/12345" }
    """
    user_email = get_user_email_from_token(authorization)

    valid_positions = ['left_link', 'centre_link', 'right_link', 'us_left_link', 'us_center_link', 'us_right_link']
    if position not in valid_positions:
        raise HTTPException(status_code=400, detail=f"Invalid position. Must be one of: {', '.join(valid_positions)}")

    try:
        logger.info(f"Updating header banner position {position} for user {user_email}")

        command = [
            "python3",
            "cms/update_header_banner.py",
            position,
            update_data.text_link_id,
            "--format", "json"
        ]

        result = await run_idc_command_async(command, cwd=IDC_TOOLS_PATH)

        logger.info(f"Successfully updated header banner position: {position}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating header banner: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# TEXT LINKS ENDPOINTS
# ============================================================================

@router.get("/api/cms/text-links")
async def list_text_links(
    authorization: Optional[str] = Header(None)
):
    """
    List all text_link metaobjects.

    Returns:
        List of text link objects with id, handle, link_text, link_location, has_image

    Example:
        GET /api/cms/text-links
    """
    user_email = get_user_email_from_token(authorization)

    try:
        logger.info(f"Listing text links for user {user_email}")

        command = [
            "python3",
            "cms/list_header_links.py",
            "--format", "json"
        ]

        result = await run_idc_command_async(command, cwd=IDC_TOOLS_PATH)

        logger.info(f"Successfully fetched {len(result)} text links")
        return {"links": result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing text links: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/cms/text-links/{identifier}")
async def update_text_link(
    identifier: str,
    update_data: TextLinkUpdate,
    authorization: Optional[str] = Header(None)
):
    """
    Update a text_link metaobject.

    Args:
        identifier: Text link handle or GID
        update_data: Fields to update (link_text, link_location, image_id)

    Returns:
        Updated text link data

    Example:
        PUT /api/cms/text-links/free-shipping-over-49
        {
            "link_text": "FREE Shipping Over $99*",
            "link_location": "/pages/shipping"
        }
    """
    user_email = get_user_email_from_token(authorization)

    try:
        logger.info(f"Updating text link {identifier} for user {user_email}")

        command = [
            "python3",
            "cms/update_header_link.py",
            identifier,
            "--format", "json"
        ]

        # Add fields to update
        if update_data.link_text is not None:
            command.extend(["--text", update_data.link_text])
        if update_data.link_location is not None:
            command.extend(["--location", update_data.link_location])
        if update_data.image_id is not None:
            command.extend(["--image-id", update_data.image_id])

        result = await run_idc_command_async(command, cwd=IDC_TOOLS_PATH)

        logger.info(f"Successfully updated text link: {identifier}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating text link: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========================================
# Image Upload Endpoint
# ========================================

@router.post("/api/cms/upload-image")
async def upload_image(
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None)
):
    """
    Upload an image file to Shopify.

    Args:
        file: Image file (jpg, png, webp, gif)
        authorization: Bearer token

    Returns:
        {
            "file_id": "gid://shopify/MediaImage/...",
            "image_url": "https://cdn.shopify.com/...",
            "filename": "uploaded-filename.webp"
        }
    """
    try:
        # Validate authorization
        if not authorization or not authorization.startswith('Bearer '):
            raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

        # Validate file type
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")

        # Save file temporarily
        import tempfile
        import shutil
        from pathlib import Path

        # Create temp file
        suffix = Path(file.filename).suffix if file.filename else '.jpg'
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_path = tmp_file.name
            # Write uploaded file to temp location
            shutil.copyfileobj(file.file, tmp_file)

        logger.info(f"Saved uploaded file to temp: {tmp_path}")

        try:
            # Use Python script to upload to Shopify
            # We'll create a generic upload script or use inline Python
            command = [
                "python3",
                "-c",
                f"""
import sys
import json
from pathlib import Path
from PIL import Image
import io
import requests

# Add bash-tools to path
sys.path.insert(0, '{IDC_TOOLS_PATH}')
from base import ShopifyClient

def upload_image(image_path):
    client = ShopifyClient()

    # Open and process image
    img = Image.open(image_path)

    # Convert to RGB if needed
    if img.mode in ('RGBA', 'LA', 'P'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
        img = background

    # Convert to WebP
    output = io.BytesIO()
    img.save(output, 'WEBP', quality=92, method=6)
    image_bytes = output.getvalue()

    filename = f"banner-upload-{{Path(image_path).stem}}.webp"

    # Stage the upload
    mutation = '''
    mutation stagedUploadsCreate($input: [StagedUploadInput!]!) {{
        stagedUploadsCreate(input: $input) {{
            stagedTargets {{
                url
                resourceUrl
                parameters {{
                    name
                    value
                }}
            }}
            userErrors {{
                field
                message
            }}
        }}
    }}
    '''

    variables = {{
        "input": [{{
            "resource": "FILE",
            "filename": filename,
            "mimeType": "image/webp",
            "httpMethod": "POST"
        }}]
    }}

    result = client.execute_graphql(mutation, variables)

    if not client.check_user_errors(result, 'stagedUploadsCreate'):
        raise Exception("Failed to stage upload")

    staged_target = result['data']['stagedUploadsCreate']['stagedTargets'][0]
    upload_url = staged_target['url']
    resource_url = staged_target['resourceUrl']
    parameters = {{param['name']: param['value'] for param in staged_target['parameters']}}

    # Upload the file
    files = {{'file': (filename, image_bytes, 'image/webp')}}
    upload_response = requests.post(upload_url, data=parameters, files=files, timeout=60)
    upload_response.raise_for_status()

    # Create file in Shopify
    create_mutation = '''
    mutation fileCreate($files: [FileCreateInput!]!) {{
        fileCreate(files: $files) {{
            files {{
                id
                ... on MediaImage {{
                    image {{
                        url
                    }}
                }}
            }}
            userErrors {{
                field
                message
            }}
        }}
    }}
    '''

    file_variables = {{
        "files": [{{
            "alt": f"Banner image - {{filename}}",
            "contentType": "IMAGE",
            "originalSource": resource_url
        }}]
    }}

    file_result = client.execute_graphql(create_mutation, file_variables)

    if not client.check_user_errors(file_result, 'fileCreate'):
        raise Exception("Failed to create file record")

    files = file_result['data']['fileCreate']['files']
    if files and len(files) > 0:
        file_id = files[0]['id']
        image_url = None
        # Safely extract image URL (may be None initially)
        if 'image' in files[0] and files[0]['image'] is not None:
            image_url = files[0]['image'].get('url')
        return {{"file_id": file_id, "image_url": image_url, "filename": filename}}

    raise Exception("No files returned from fileCreate")

result = upload_image('{tmp_path}')
print(json.dumps(result))
"""
            ]

            # Run the inline Python script
            result = await run_idc_command_async(command, cwd=IDC_TOOLS_PATH)

            logger.info(f"Image uploaded successfully: {result.get('file_id')}")
            return result

        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except:
                pass

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading image: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# MENU MANAGEMENT ENDPOINTS
# ============================================================================

class MenuUpdate(BaseModel):
    """Model for menu updates"""
    title: Optional[str] = None
    items: List[Dict[str, Any]]  # Structured menu items (parsed format)


@router.get("/api/cms/menus")
async def list_menus(authorization: Optional[str] = Header(None)):
    """
    List all menus in the store.

    Returns:
        {
            "success": true,
            "menus": [
                {
                    "id": "gid://shopify/Menu/123",
                    "handle": "main-menu",
                    "title": "Main Menu",
                    "itemCount": 15
                },
                ...
            ]
        }
    """
    try:
        # Verify user authentication
        user_email = get_user_email_from_token(authorization)
        logger.info(f"User {user_email} listing menus")

        # Run cms/get_menu.py --list
        command = ["python3", "cms/get_menu.py", "--list", "--output-format", "json"]
        result = await run_idc_command_async(command, cwd=IDC_TOOLS_PATH)

        if not result.get("success"):
            raise HTTPException(status_code=500, detail="Failed to list menus")

        menus = result.get("menus", [])

        # Filter to only show editable menus (top-mega-menu and hydrogen-footer)
        allowed_handles = ["top-mega-menu", "hydrogen-footer"]
        menus = [menu for menu in menus if menu.get("handle") in allowed_handles]

        # For each menu, get item count
        menus_with_counts = []
        for menu in menus:
            # We don't have item counts in list view, so we'll fetch each menu
            # This could be optimized later, but for now it's acceptable (usually < 20 menus)
            try:
                menu_detail_cmd = ["python3", "cms/get_menu.py", "--id", menu["id"], "--output-format", "json"]
                menu_detail = await run_idc_command_async(menu_detail_cmd, cwd=IDC_TOOLS_PATH)

                if menu_detail.get("success"):
                    menu_data = menu_detail.get("menu", {})
                    # Count total items recursively
                    def count_items(items):
                        count = len(items)
                        for item in items:
                            if item.get("items"):
                                count += count_items(item["items"])
                        return count

                    item_count = count_items(menu_data.get("items", []))
                    menus_with_counts.append({
                        **menu,
                        "itemCount": item_count
                    })
                else:
                    menus_with_counts.append({**menu, "itemCount": 0})
            except Exception as e:
                logger.warning(f"Error getting item count for menu {menu['id']}: {e}")
                menus_with_counts.append({**menu, "itemCount": 0})

        return {
            "success": True,
            "menus": menus_with_counts
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing menus: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/cms/menus/{menu_id:path}")
async def get_menu(
    menu_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Get specific menu with parsed patterns.

    Args:
        menu_id: Menu ID (URL-encoded GID or handle)

    Returns:
        {
            "success": true,
            "menu": {
                "id": "gid://...",
                "handle": "top-mega-menu",
                "title": "Top-Mega-Menu",
                "items": [...] # Parsed with structured pattern data
            }
        }
    """
    try:
        # Verify user authentication
        user_email = get_user_email_from_token(authorization)
        logger.info(f"User {user_email} getting menu {menu_id}")

        # Decode menu_id if URL-encoded
        import urllib.parse
        menu_id_decoded = urllib.parse.unquote(menu_id)

        # Determine if it's a GID or handle
        if menu_id_decoded.startswith("gid://"):
            command = ["python3", "cms/get_menu.py", "--id", menu_id_decoded, "--output-format", "json"]
        else:
            command = ["python3", "cms/get_menu.py", "--handle", menu_id_decoded, "--output-format", "json"]

        # Get menu data
        result = await run_idc_command_async(command, cwd=IDC_TOOLS_PATH)

        if not result.get("success"):
            raise HTTPException(status_code=404, detail=f"Menu not found: {menu_id}")

        menu_data = result.get("menu")

        # Parse patterns using cms/parse_menu_patterns.py
        # Write menu data to temp file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(menu_data, f)
            temp_file = f.name

        try:
            # Parse patterns
            parse_cmd = ["python3", "cms/parse_menu_patterns.py", "--parse-file", temp_file, "--output-format", "json"]
            parsed_result = await run_idc_command_async(parse_cmd, cwd=IDC_TOOLS_PATH)

            return {
                "success": True,
                "menu": parsed_result  # Returns parsed menu with structured items
            }
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_file)
            except:
                pass

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting menu {menu_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/cms/menus/{menu_id:path}")
async def update_menu(
    menu_id: str,
    update_data: MenuUpdate,
    authorization: Optional[str] = Header(None)
):
    """
    Update menu structure.

    Args:
        menu_id: Menu ID (URL-encoded GID)
        update_data: Menu update data with structured items

    Returns:
        {
            "success": true,
            "menu": {...}  # Updated menu data
        }
    """
    try:
        # Verify user authentication
        user_email = get_user_email_from_token(authorization)
        logger.info(f"User {user_email} updating menu {menu_id}")

        # Decode menu_id if URL-encoded
        import urllib.parse
        menu_id_decoded = urllib.parse.unquote(menu_id)

        if not menu_id_decoded.startswith("gid://"):
            raise HTTPException(status_code=400, detail="Menu ID must be a GID")

        # Encode structured items back to Shopify format using cms/parse_menu_patterns.py
        # Prepare menu data for encoding
        menu_to_encode = {
            "items": update_data.items
        }
        if update_data.title:
            menu_to_encode["title"] = update_data.title

        # Write to temp file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(menu_to_encode, f)
            temp_input_file = f.name

        try:
            # Encode patterns
            encode_cmd = [
                "python3", "cms/parse_menu_patterns.py",
                "--encode-file", temp_input_file,
                "--validate"
            ]
            encoded_result = await run_idc_command_async(encode_cmd, cwd=IDC_TOOLS_PATH)

            # Parse the encoded result
            # The script prints to stdout, so we need to parse the output string
            output = encoded_result.get("output", "")

            # Extract JSON from output (it's after the validation message)
            try:
                # Find the JSON object in the output
                json_start = output.find("{")
                if json_start == -1:
                    raise ValueError("No JSON found in output")

                json_str = output[json_start:]
                encoded_menu = json.loads(json_str)
                encoded_items = encoded_menu.get("items", [])

                if not encoded_items:
                    raise ValueError("No items in encoded menu")

            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Failed to parse encoded output: {e}")
                logger.error(f"Output: {output[:500]}")
                raise HTTPException(status_code=500, detail=f"Failed to parse encoded menu: {str(e)}")

            # Write encoded items to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(encoded_items, f, indent=2)
                temp_encoded_file = f.name

            try:
                # Update menu using update_menu.py
                update_cmd = [
                    "python3", "cms/update_menu.py",
                    "--id", menu_id_decoded,
                    "--items-file", temp_encoded_file,
                    "--validate",
                    "--output-format", "json"
                ]

                result = await run_idc_command_async(update_cmd, cwd=IDC_TOOLS_PATH)

                if not result.get("success"):
                    raise HTTPException(status_code=500, detail="Failed to update menu")

                return result

            finally:
                try:
                    os.unlink(temp_encoded_file)
                except:
                    pass

        finally:
            try:
                os.unlink(temp_input_file)
            except:
                pass

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating menu {menu_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
