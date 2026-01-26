"""
Product Matching Service

Provides product matching algorithms and operations including:
- Automatic product matching with multi-factor similarity scoring
- Manual product matching
- Embedding-based similarity calculation
- Match management (CRUD operations)
"""

from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone
from utils.datetime_utils import utc_now_naive
from decimal import Decimal
import math
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_, or_, delete
from sqlalchemy.orm import selectinload
from database import (
    IdcProduct, CompetitorProduct, ProductMatch, Competitor, 
    MonitoredBrand, PriceAlert
)
from database.session import AsyncSessionLocal
from uuid import uuid4
import logging
import re

logger = logging.getLogger(__name__)

class ProductMatcher:
    """Product matching algorithm with multi-factor similarity scoring"""
    
    def __init__(self):
        # Hybrid approach: 40% embeddings + 60% traditional factors
        self.weights = {
            'embedding': 0.4,    # 40% weight on semantic similarity  
            'title': 0.18,       # 18% weight on title similarity
            'vendor': 0.24,      # 24% weight on vendor matching
            'price': 0.06,       # 6% weight on price proximity
            'sku': 0.0,          # Disabled
            'type': 0.12         # 12% weight on product type
        }
        
        self.thresholds = {
            'high_confidence': 0.80,    # 80%+ = very likely match
            'medium_confidence': 0.70,  # 70-79% = possible match
            'low_confidence': 0.60      # 60-69% = weak match
        }
    
    def calculate_string_similarity(self, str1: Optional[str], str2: Optional[str]) -> float:
        """Calculate string similarity using Levenshtein distance"""
        if not str1 or not str2:
            return 0.0
        
        str1 = str1.lower().strip()
        str2 = str2.lower().strip()
        
        if str1 == str2:
            return 1.0
        
        # Calculate Levenshtein distance
        len1, len2 = len(str1), len(str2)
        matrix = [[0] * (len2 + 1) for _ in range(len1 + 1)]
        
        # Initialize first row and column
        for i in range(len1 + 1):
            matrix[i][0] = i
        for j in range(len2 + 1):
            matrix[0][j] = j
        
        # Fill matrix
        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                if str1[i-1] == str2[j-1]:
                    matrix[i][j] = matrix[i-1][j-1]
                else:
                    matrix[i][j] = min(
                        matrix[i-1][j-1] + 1,  # substitution
                        matrix[i][j-1] + 1,    # insertion
                        matrix[i-1][j] + 1     # deletion
                    )
        
        max_len = max(len1, len2)
        return (max_len - matrix[len1][len2]) / max_len if max_len > 0 else 0.0
    
    def calculate_title_similarity(self, title1: Optional[str], title2: Optional[str]) -> float:
        """Enhanced title similarity with brand and model extraction"""
        if not title1 or not title2:
            return 0.0
        
        # Basic string similarity
        basic_similarity = self.calculate_string_similarity(title1, title2)
        
        # Extract key terms (remove common words)
        stop_words = {'the', 'and', 'or', 'with', 'for', 'espresso', 'coffee', 'machine', 'grinder'}
        
        def extract_key_terms(title: str) -> List[str]:
            # Remove punctuation and split
            clean_title = re.sub(r'[^\w\s]', ' ', title.lower())
            words = clean_title.split()
            # Filter out stop words and short words
            return sorted([word for word in words if len(word) > 2 and word not in stop_words])
        
        terms1 = extract_key_terms(title1)
        terms2 = extract_key_terms(title2)
        
        # Calculate term overlap
        if not terms1 or not terms2:
            return basic_similarity
        
        common_terms = set(terms1) & set(terms2)
        term_similarity = len(common_terms) / max(len(terms1), len(terms2))
        
        # Weighted combination
        return (basic_similarity * 0.6) + (term_similarity * 0.4)
    
    def calculate_vendor_similarity(self, vendor1: Optional[str], vendor2: Optional[str]) -> float:
        """Vendor similarity (exact match gets higher score)"""
        if not vendor1 or not vendor2:
            return 0.0
        
        v1 = vendor1.lower().strip()
        v2 = vendor2.lower().strip()
        
        # Exact match
        if v1 == v2:
            return 1.0
        
        # Check if one vendor contains the other
        if v1 in v2 or v2 in v1:
            return 0.8
        
        # String similarity fallback
        return self.calculate_string_similarity(v1, v2)
    
    def calculate_price_similarity(self, price1: Optional[Decimal], price2: Optional[Decimal]) -> float:
        """Price similarity based on relative difference"""
        if not price1 or not price2 or price1 <= 0 or price2 <= 0:
            return 0.0
        
        p1, p2 = float(price1), float(price2)
        price_diff = abs(p1 - p2)
        avg_price = (p1 + p2) / 2
        relative_error = price_diff / avg_price if avg_price > 0 else 1.0
        
        # More generous similarity for price matching
        if relative_error <= 0.05:
            return 1.0      # 5% difference = perfect
        elif relative_error <= 0.15:
            return 0.8      # 15% difference = good
        elif relative_error <= 0.30:
            return 0.6      # 30% difference = fair
        elif relative_error <= 0.50:
            return 0.4      # 50% difference = poor
        
        return max(0.0, 1.0 - relative_error)
    
    def calculate_sku_similarity(self, sku1: Optional[str], sku2: Optional[str]) -> float:
        """SKU similarity"""
        if not sku1 or not sku2:
            return 0.0
        
        # Exact match
        if sku1.lower() == sku2.lower():
            return 1.0
        
        # Extract alphanumeric parts
        def extract_alphanumeric(sku: str) -> str:
            return re.sub(r'[^a-zA-Z0-9]', '', sku).lower()
        
        clean1 = extract_alphanumeric(sku1)
        clean2 = extract_alphanumeric(sku2)
        
        if clean1 == clean2:
            return 0.9
        
        return self.calculate_string_similarity(clean1, clean2)
    
    def calculate_type_similarity(self, type1: Optional[str], type2: Optional[str]) -> float:
        """Product type similarity"""
        if not type1 or not type2:
            return 0.0
        
        t1 = type1.lower().strip()
        t2 = type2.lower().strip()
        
        if t1 == t2:
            return 1.0
        
        # Category matching
        categories = {
            'espresso': ['espresso-machines', 'coffee-machines', 'automatic', 'semi-automatic'],
            'grinder': ['grinders', 'burr-grinder', 'coffee-grinder'],
            'accessory': ['accessories', 'parts', 'cleaning']
        }
        
        for category, terms in categories.items():
            if any(term in t1 for term in terms) and any(term in t2 for term in terms):
                return 0.8
        
        return self.calculate_string_similarity(t1, t2)
    
    def calculate_embedding_similarity(self, embedding1: Optional[str], embedding2: Optional[str]) -> float:
        """Calculate embedding similarity using cosine similarity"""
        if not embedding1 or not embedding2:
            return 0.0
        
        try:
            # Parse JSON embedding strings
            import json
            import numpy as np
            
            emb1 = json.loads(embedding1)
            emb2 = json.loads(embedding2)
            
            # Convert to numpy arrays
            vec1 = np.array(emb1)
            vec2 = np.array(emb2)
            
            # Calculate cosine similarity
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
                
            similarity = dot_product / (norm1 * norm2)
            
            # Ensure result is between 0 and 1
            return max(0.0, min(1.0, similarity))
            
        except Exception as e:
            logger.warning(f"Error calculating embedding similarity: {e}")
            return 0.0
    
    def calculate_similarity(self, idc_product: IdcProduct, competitor_product: CompetitorProduct) -> Dict[str, Any]:
        """Calculate overall similarity score"""
        title_score = self.calculate_title_similarity(idc_product.title, competitor_product.title)
        vendor_score = self.calculate_vendor_similarity(idc_product.vendor, competitor_product.vendor)
        price_score = self.calculate_price_similarity(idc_product.price, competitor_product.price)
        sku_score = self.calculate_sku_similarity(idc_product.sku, competitor_product.sku)
        type_score = self.calculate_type_similarity(idc_product.product_type, competitor_product.product_type)
        embedding_score = self.calculate_embedding_similarity(idc_product.embedding, competitor_product.embedding)
        
        # Ensure all scores are between 0 and 1
        scores = {
            'title_score': max(0.0, min(1.0, title_score)),
            'vendor_score': max(0.0, min(1.0, vendor_score)),
            'price_score': max(0.0, min(1.0, price_score)),
            'sku_score': max(0.0, min(1.0, sku_score)),
            'type_score': max(0.0, min(1.0, type_score)),
            'embedding_score': max(0.0, min(1.0, embedding_score))
        }
        
        # Calculate weighted overall score
        overall_score = (
            (scores['embedding_score'] * self.weights['embedding']) +
            (scores['title_score'] * self.weights['title']) +
            (scores['vendor_score'] * self.weights['vendor']) +
            (scores['price_score'] * self.weights['price']) +
            (scores['sku_score'] * self.weights['sku']) +
            (scores['type_score'] * self.weights['type'])
        )
        
        overall_score = max(0.0, min(1.0, overall_score))  # Clamp final score
        
        return {
            'overall_score': overall_score,
            'embedding_similarity': scores['embedding_score'],
            'title_similarity': scores['title_score'],
            'brand_similarity': scores['vendor_score'],
            'price_similarity': scores['price_score'],
            'sku_similarity': scores['sku_score'],
            'type_similarity': scores['type_score'],
            'confidence_level': self.get_confidence_level(overall_score)
        }
    
    def get_confidence_level(self, score: float) -> str:
        """Get confidence level based on score"""
        if score >= self.thresholds['high_confidence']:
            return 'high'
        elif score >= self.thresholds['medium_confidence']:
            return 'medium'
        elif score >= self.thresholds['low_confidence']:
            return 'low'
        return 'very_low'

class ProductMatchingService:
    """Service for product matching operations"""
    
    def __init__(self):
        self.session_local = AsyncSessionLocal
        self.matcher = ProductMatcher()
    
    async def auto_match_products(
        self,
        brands: Optional[List[str]] = None,
        min_confidence: str = 'medium',
        dry_run: bool = False
    ) -> Dict:
        """Match products automatically using similarity algorithms"""
        from database import RejectedMatch

        async with self.session_local() as session:
            try:
                logger.info("Starting automatic product matching (incremental mode)...")

                # OPTIMIZATION: Don't delete existing matches - reuse them!
                # This saves massive amounts of time by not re-matching already matched products

                # Load rejected pairs into a set for fast lookups
                rejected_pairs_query = select(RejectedMatch.idc_product_id, RejectedMatch.competitor_product_id)
                rejected_result = await session.execute(rejected_pairs_query)
                rejected_pairs = {(idc_id, comp_id) for idc_id, comp_id in rejected_result}

                logger.info(f"Loaded {len(rejected_pairs)} rejected product pairs")

                # Load ALL existing matches (manual + automated) to avoid duplicates
                all_matches_query = select(
                    ProductMatch.idc_product_id,
                    ProductMatch.competitor_product_id,
                    ProductMatch.is_manual_match
                )
                all_matches_result = await session.execute(all_matches_query)
                existing_pairs = {(idc_id, comp_id) for idc_id, comp_id, _ in all_matches_result}

                # Also track manual matches separately for logging
                manual_matches_query = select(ProductMatch.idc_product_id, ProductMatch.competitor_product_id).where(
                    ProductMatch.is_manual_match == True
                )
                manual_matches_result = await session.execute(manual_matches_query)
                existing_manual_pairs = {(idc_id, comp_id) for idc_id, comp_id in manual_matches_result}

                logger.info(f"Loaded {len(existing_pairs)} existing matches to skip ({len(existing_manual_pairs)} manual, {len(existing_pairs) - len(existing_manual_pairs)} automated)")
                logger.info(f"Will only create matches for new/unmatched product pairs")

                results = {
                    'total_processed': 0,
                    'matches_found': 0,
                    'matches_created': 0,
                    'matches_reused': 0,
                    'skipped_rejected': 0,
                    'high_confidence': 0,
                    'medium_confidence': 0,
                    'low_confidence': 0,
                    'matches': []
                }

                # Track matches created for batch commits
                matches_since_commit = 0
                BATCH_COMMIT_SIZE = 20  # Commit every 20 matches

                # Get iDC products to match
                idc_query = select(IdcProduct)
                if brands:
                    idc_query = idc_query.where(IdcProduct.vendor.in_(brands))

                idc_result = await session.execute(idc_query)
                idc_products = idc_result.scalars().all()

                logger.info(f"Processing {len(idc_products)} iDC products")

                # Get all competitor products for batch processing
                competitor_result = await session.execute(select(CompetitorProduct))
                competitor_products = competitor_result.scalars().all()

                logger.info(f"Loaded {len(competitor_products)} competitor products")

                # Process each iDC product
                for idc_product in idc_products:
                    best_match = None
                    best_score = 0.0

                    # Compare against all competitor products
                    for competitor_product in competitor_products:
                        # Skip rejected pairs
                        if (idc_product.id, competitor_product.id) in rejected_pairs:
                            continue

                        similarity = self.matcher.calculate_similarity(idc_product, competitor_product)

                        if (similarity['overall_score'] > best_score and
                            similarity['confidence_level'] != 'very_low'):
                            best_match = {
                                'competitor_product': competitor_product,
                                'similarity': similarity
                            }
                            best_score = similarity['overall_score']

                    # Check if best match is rejected
                    if best_match and (idc_product.id, best_match['competitor_product'].id) in rejected_pairs:
                        results['skipped_rejected'] += 1
                        results['total_processed'] += 1
                        continue

                    # Check if this product pair already has a match (manual or automated)
                    if best_match and (idc_product.id, best_match['competitor_product'].id) in existing_pairs:
                        logger.debug(
                            f"Skipping {idc_product.title} → {best_match['competitor_product'].title} "
                            f"(already matched)"
                        )
                        results['matches_reused'] += 1
                        results['total_processed'] += 1
                        continue

                    if best_match and self._meets_min_confidence(
                        best_match['similarity']['confidence_level'], min_confidence
                    ):
                        results['matches_found'] += 1
                        results['matches_created'] += 1
                        results[best_match['similarity']['confidence_level'] + '_confidence'] += 1

                        logger.info(
                            f"Creating match: {idc_product.title} → "
                            f"{best_match['competitor_product'].title} "
                            f"({best_match['similarity']['overall_score']*100:.1f}%)"
                        )

                        if not dry_run:
                            # Create match record
                            match_data = ProductMatch(
                                id=f"{idc_product.id}_{best_match['competitor_product'].id}",
                                idc_product_id=idc_product.id,
                                competitor_product_id=best_match['competitor_product'].id,
                                overall_score=best_match['similarity']['overall_score'],
                                embedding_similarity=best_match['similarity']['embedding_similarity'],
                                title_similarity=best_match['similarity']['title_similarity'],
                                brand_similarity=best_match['similarity']['brand_similarity'],
                                price_similarity=best_match['similarity']['price_similarity'],
                                confidence_level=best_match['similarity']['confidence_level'],
                                is_manual_match=False,
                                created_at=utc_now_naive(),
                                updated_at=utc_now_naive()
                            )

                            session.add(match_data)
                            matches_since_commit += 1

                            # Batch commit to prevent data loss from interruptions
                            if matches_since_commit >= BATCH_COMMIT_SIZE:
                                await session.commit()
                                logger.info(f"Batch committed {matches_since_commit} matches")
                                matches_since_commit = 0

                        # Add to results
                        results['matches'].append({
                            'idc_product': {
                                'title': idc_product.title,
                                'vendor': idc_product.vendor,
                                'sku': idc_product.sku,
                                'price': float(idc_product.price) if idc_product.price else 0
                            },
                            'competitor_product': {
                                'title': best_match['competitor_product'].title,
                                'vendor': best_match['competitor_product'].vendor,
                                'sku': best_match['competitor_product'].sku,
                                'price': float(best_match['competitor_product'].price) if best_match['competitor_product'].price else 0,
                                'competitor': best_match['competitor_product'].competitor_id
                            },
                            'similarity': best_match['similarity']
                        })
                    
                    results['total_processed'] += 1

                # Final commit for any remaining matches
                if not dry_run and matches_since_commit > 0:
                    await session.commit()
                    logger.info(f"Final commit of {matches_since_commit} remaining matches")

                logger.info(
                    f"Matching completed: {results['matches_found']} matches found "
                    f"from {results['total_processed']} products"
                )
                
                return {
                    'message': f"Product matching completed{' (dry run)' if dry_run else ''}",
                    **results
                }
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Error in automatic product matching: {e}")
                raise
    
    async def create_manual_match(
        self,
        idc_product_id: str,
        competitor_product_id: str,
        confidence_override: Optional[str] = None
    ) -> Dict:
        """Create a manual product match"""
        async with self.session_local() as session:
            try:
                # Get products
                idc_product = await session.get(IdcProduct, idc_product_id)
                competitor_product = await session.get(CompetitorProduct, competitor_product_id)
                
                if not idc_product or not competitor_product:
                    raise ValueError("One or both products not found")
                
                # Calculate similarity
                similarity = self.matcher.calculate_similarity(idc_product, competitor_product)
                
                # Create manual match
                match_data = ProductMatch(
                    id=f"{idc_product_id}_{competitor_product_id}",
                    idc_product_id=idc_product_id,
                    competitor_product_id=competitor_product_id,
                    overall_score=similarity['overall_score'],
                    embedding_similarity=similarity['embedding_similarity'],
                    title_similarity=similarity['title_similarity'],
                    brand_similarity=similarity['brand_similarity'],
                    price_similarity=similarity['price_similarity'],
                    confidence_level=confidence_override or similarity['confidence_level'],
                    is_manual_match=True,
                    created_at=utc_now_naive(),
                    updated_at=utc_now_naive()
                )
                
                session.add(match_data)
                await session.commit()
                await session.refresh(match_data)
                
                logger.info(f"Created manual match: {idc_product.title} → {competitor_product.title}")
                
                return {
                    'message': 'Manual product match created successfully',
                    'match': match_data.__dict__,
                    'similarity': similarity
                }
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Error creating manual match: {e}")
                raise
    
    async def create_perfect_match(
        self,
        idc_product_id: str,
        competitor_product_id: str
    ) -> Dict:
        """Create a perfect manual match with 100% scores"""
        async with self.session_local() as session:
            try:
                # Get products
                idc_product = await session.get(IdcProduct, idc_product_id)
                competitor_product = await session.get(CompetitorProduct, competitor_product_id)
                
                if not idc_product or not competitor_product:
                    raise ValueError("One or both products not found")
                
                # Create perfect match with 100% scores
                match_data = ProductMatch(
                    id=f"{idc_product_id}_{competitor_product_id}",
                    idc_product_id=idc_product_id,
                    competitor_product_id=competitor_product_id,
                    overall_score=1.0,
                    embedding_similarity=1.0,
                    title_similarity=1.0,
                    brand_similarity=1.0,
                    price_similarity=1.0,
                    confidence_level='high',
                    is_manual_match=True,
                    created_at=utc_now_naive(),
                    updated_at=utc_now_naive()
                )
                
                session.add(match_data)
                await session.commit()
                await session.refresh(match_data)
                
                logger.info(f"Created perfect match: {idc_product.title} → {competitor_product.title}")
                
                return {
                    'message': 'Perfect manual match created successfully',
                    'match': match_data.__dict__,
                    'idc_product': idc_product.__dict__,
                    'competitor_product': competitor_product.__dict__
                }
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Error creating perfect match: {e}")
                raise
    
    async def get_matches(
        self,
        confidence_level: Optional[str] = None,
        brand: Optional[str] = None,
        has_violations: Optional[bool] = None,
        page: int = 1,
        limit: int = 50
    ) -> Dict:
        """Get product matches with filtering and pagination"""
        async with self.session_local() as session:
            try:
                offset = (page - 1) * limit
                
                query = select(ProductMatch).options(
                    selectinload(ProductMatch.idc_product),
                    selectinload(ProductMatch.competitor_product).selectinload(CompetitorProduct.competitor),
                    selectinload(ProductMatch.price_alerts)
                )
                
                # Apply filters
                if confidence_level:
                    query = query.where(ProductMatch.confidence_level == confidence_level)
                
                if brand:
                    query = query.join(IdcProduct).where(IdcProduct.vendor == brand)
                
                if has_violations:
                    query = query.join(PriceAlert).where(
                        ~PriceAlert.status.in_(['resolved', 'dismissed'])
                    )
                
                # Order by manual matches first, then by confidence and score
                query = query.order_by(
                    desc(ProductMatch.is_manual_match),
                    desc(ProductMatch.confidence_level),
                    desc(ProductMatch.overall_score)
                )
                
                # Get paginated results
                matches_result = await session.execute(query.offset(offset).limit(limit))
                matches = matches_result.scalars().all()
                
                # Get total count
                count_query = select(func.count(ProductMatch.id))
                if confidence_level:
                    count_query = count_query.where(ProductMatch.confidence_level == confidence_level)
                if brand:
                    count_query = count_query.join(IdcProduct).where(IdcProduct.vendor == brand)
                if has_violations:
                    count_query = count_query.join(PriceAlert).where(
                        ~PriceAlert.status.in_(['resolved', 'dismissed'])
                    )
                
                total_count = await session.scalar(count_query)
                
                # Format matches with related data
                formatted_matches = []
                for match in matches:
                    formatted_match = {
                        **match.__dict__,
                        'idc_products': match.idc_product.__dict__ if match.idc_product else None,
                        'competitor_products': {
                            **match.competitor_product.__dict__,
                            'competitors': match.competitor_product.competitor.__dict__ if match.competitor_product.competitor else None
                        } if match.competitor_product else None,
                        'price_alerts': [
                            alert.__dict__ for alert in match.price_alerts 
                            if alert.status not in ['resolved', 'dismissed']
                        ]
                    }
                    formatted_matches.append(formatted_match)
                
                return {
                    'matches': formatted_matches,
                    'pagination': {
                        'page': page,
                        'limit': limit,
                        'total': total_count or 0,
                        'total_pages': math.ceil((total_count or 0) / limit),
                        'has_next': offset + limit < (total_count or 0),
                        'has_prev': page > 1
                    }
                }
                
            except Exception as e:
                logger.error(f"Error fetching matches: {e}")
                raise
    
    async def delete_match(self, match_id: str) -> bool:
        """Delete a product match"""
        async with self.session_local() as session:
            try:
                match = await session.get(ProductMatch, match_id)
                if not match:
                    return False

                await session.delete(match)
                await session.commit()

                logger.info(f"Deleted product match: {match_id}")
                return True

            except Exception as e:
                await session.rollback()
                logger.error(f"Error deleting match {match_id}: {e}")
                raise

    async def verify_match(self, match_id: str, verified_by: Optional[str] = None) -> Dict:
        """Verify/approve an auto match, converting it to a manual match.

        This upgrades an automatically-matched product pair to a manual match,
        indicating human approval and preventing future auto-matching changes.

        Args:
            match_id: ID of the product match to verify
            verified_by: Optional username/email of the person verifying

        Returns:
            Dict with success status and match details
        """
        async with self.session_local() as session:
            try:
                # Fetch match with relationships
                match_query = select(ProductMatch).options(
                    selectinload(ProductMatch.idc_product),
                    selectinload(ProductMatch.competitor_product).options(
                        selectinload(CompetitorProduct.competitor)
                    )
                ).where(ProductMatch.id == match_id)

                result = await session.execute(match_query)
                match = result.scalar_one_or_none()

                if not match:
                    raise ValueError(f"Product match {match_id} not found")

                # Update to manual match with perfect confidence
                was_manual = match.is_manual_match
                match.is_manual_match = True
                match.confidence_level = 'high'
                match.overall_score = 1.0
                match.updated_at = utc_now_naive()

                await session.commit()

                logger.info(
                    f"{'Already verified' if was_manual else 'Verified'} product match {match_id}"
                    f"{f' by {verified_by}' if verified_by else ''}"
                )

                return {
                    'success': True,
                    'message': f"Product match {'was already verified' if was_manual else 'verified successfully'}",
                    'match': {
                        'id': match.id,
                        'idc_product': {
                            'title': match.idc_product.title,
                            'vendor': match.idc_product.vendor
                        } if match.idc_product else None,
                        'competitor_product': {
                            'title': match.competitor_product.title,
                            'competitor': match.competitor_product.competitor.name
                        } if match.competitor_product and match.competitor_product.competitor else None,
                        'is_manual_match': match.is_manual_match,
                        'confidence_level': match.confidence_level,
                        'overall_score': match.overall_score
                    }
                }

            except ValueError:
                raise
            except Exception as e:
                await session.rollback()
                logger.error(f"Error verifying match {match_id}: {e}")
                raise

    async def reject_match(
        self,
        match_id: str,
        reason: Optional[str] = None,
        rejected_by: Optional[str] = None
    ) -> Dict:
        """Reject a product match and blacklist the pair from future auto-matching.

        This deletes the match and adds the product pair to rejected_matches table
        to prevent them from being automatically matched again.

        Args:
            match_id: ID of the product match to reject
            reason: Optional reason for rejection
            rejected_by: Optional username/email of the person rejecting

        Returns:
            Dict with success status and details
        """
        from database import RejectedMatch

        async with self.session_local() as session:
            try:
                # Fetch match with relationships
                match_query = select(ProductMatch).options(
                    selectinload(ProductMatch.idc_product),
                    selectinload(ProductMatch.competitor_product).options(
                        selectinload(CompetitorProduct.competitor)
                    )
                ).where(ProductMatch.id == match_id)

                result = await session.execute(match_query)
                match = result.scalar_one_or_none()

                if not match:
                    raise ValueError(f"Product match {match_id} not found")

                idc_product_id = match.idc_product_id
                competitor_product_id = match.competitor_product_id

                # Check if already rejected
                existing_rejection = await session.execute(
                    select(RejectedMatch).where(
                        and_(
                            RejectedMatch.idc_product_id == idc_product_id,
                            RejectedMatch.competitor_product_id == competitor_product_id
                        )
                    )
                )

                if existing_rejection.scalar_one_or_none():
                    # Already rejected, just delete the match
                    await session.delete(match)
                    await session.commit()

                    return {
                        'success': True,
                        'message': 'Match deleted (pair was already rejected)',
                        'already_rejected': True
                    }

                # Create rejected match record
                rejected_match = RejectedMatch(
                    id=str(uuid4()),
                    idc_product_id=idc_product_id,
                    competitor_product_id=competitor_product_id,
                    rejected_reason=reason or 'Unmatched via UI',
                    rejected_by=rejected_by,
                    rejected_at=utc_now_naive(),
                    created_at=utc_now_naive()
                )

                session.add(rejected_match)

                # Delete the match
                await session.delete(match)

                await session.commit()

                logger.info(
                    f"Rejected product match {match_id} and blacklisted pair"
                    f"{f' by {rejected_by}' if rejected_by else ''}"
                )

                return {
                    'success': True,
                    'message': 'Match rejected and pair blacklisted from future auto-matching',
                    'rejected_match': {
                        'idc_product': {
                            'title': match.idc_product.title,
                            'vendor': match.idc_product.vendor
                        } if match.idc_product else None,
                        'competitor_product': {
                            'title': match.competitor_product.title,
                            'competitor': match.competitor_product.competitor.name
                        } if match.competitor_product and match.competitor_product.competitor else None
                    }
                }

            except ValueError:
                raise
            except Exception as e:
                await session.rollback()
                logger.error(f"Error rejecting match {match_id}: {e}")
                raise
    
    async def clear_all_matches(self, include_manual: bool = False) -> Dict:
        """Clear product matches (automated by default, optionally manual)"""
        async with self.session_local() as session:
            try:
                # Count manual matches that will be preserved
                manual_count = 0
                if not include_manual:
                    manual_count = await session.scalar(
                        select(func.count(ProductMatch.id)).where(ProductMatch.is_manual_match == True)
                    )
                
                # Delete matches based on include_manual flag
                if include_manual:
                    deleted_result = await session.execute(delete(ProductMatch))
                else:
                    deleted_result = await session.execute(
                        delete(ProductMatch).where(ProductMatch.is_manual_match == False)
                    )
                
                await session.commit()
                
                logger.info(
                    f"Cleared {deleted_result.rowcount} {'all' if include_manual else 'automated'} matches"
                )
                
                return {
                    'message': f"Cleared {deleted_result.rowcount} {'all' if include_manual else 'automated'} product matches",
                    'cleared_count': deleted_result.rowcount,
                    'preserved_manual_matches': manual_count
                }
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Error clearing matches: {e}")
                raise
    
    def _meets_min_confidence(self, level: str, min_level: str) -> bool:
        """Check if confidence level meets minimum requirement"""
        levels = {'low': 1, 'medium': 2, 'high': 3}
        return levels.get(level, 0) >= levels.get(min_level, 0)
