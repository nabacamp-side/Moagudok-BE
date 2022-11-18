from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import viewsets, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import ErrorDetail

from django.db import transaction
from django.db.models import Q, F
from sharedb.models import Category, Product
from .serializers import CategoryListSerializer, ProductListSerializer, ProductDetailSerializer
from constants import COOKIE_KEY_NAME, EXPIRED_TIME, STANDARD_NUM_OF_PRODUCTS, PER_PAGE_SIZE, DEBUG_PRINT

# url : /consumer/product/category
class ProductCategoryListView(APIView):
    def get(self, request):
        category_data = Category.objects.all()
        CategorySerializer_data = CategoryListSerializer(category_data, many=True).data
        return Response(CategorySerializer_data, status.HTTP_200_OK)

class ProductListPaginationClass(PageNumberPagination): # 
    page_size = PER_PAGE_SIZE # settings.py의 Default 값 변경

# url : /consumer/product/list?category=1&search&page=1
class ProductListPaginationViewSet(viewsets.ModelViewSet):
    serializer_class = ProductListSerializer
    pagination_class = ProductListPaginationClass
    queryset = Product.objects.all()
    def get_queryset(self):
        condition = Q()
        category_id = self.request.query_params['category']
        search_text = self.request.query_params['search']
        if category_id:
            condition.add(Q(category_id = category_id), condition.AND)
        if search_text:
            mini_q = Q()
            mini_q.add(Q(product_name__icontains = search_text), condition.OR) # product_name - 대소문자 구분 X 검색
            mini_q.add(Q(product_group_name__icontains = search_text), condition.OR) # product_group_name - 대소문자 구분 X 검색
            condition.add(mini_q, condition.AND)
        query_set = self.queryset.filter(condition)
        return query_set

# url : /consumer/product/detail/{product_id}
class ProductDetailView(APIView):
    @transaction.atomic
    def get(self, request, product_id):
        try:
            detail_product = Product.objects.get(id = product_id)
        except:
            return Response(ErrorDetail(string = '존재하지 않는 구독 상품 입니다.', code=404), status=status.HTTP_404_NOT_FOUND)

        # Cookies에 담긴 product id list
        try: # Cookies 존재시
            cookies = request.headers['Cookie']
            cookies = cookies.split(';')
            if DEBUG_PRINT: print('Cookies List : ', cookies)
            p_id_list = [int(cookie.strip().replace(COOKIE_KEY_NAME, '').replace('=T','')) for cookie in cookies if COOKIE_KEY_NAME in cookie]
        except: # cookie 없으면
            p_id_list = []

        # 현재 상품 product_id 방문이력 없으면
        if product_id not in p_id_list:
            detail_product.views = F("views") + 1
            detail_product.save()
            detail_product.refresh_from_db() # save 한 DB 재 호출
            
        # Serializers
        detail_product_data = ProductDetailSerializer(detail_product).data

        # Response Cookie Settings
        response = Response(detail_product_data, status=status.HTTP_200_OK)

        # 현재 상품 product_id 방문이력 없을 때만
        if product_id not in p_id_list:
            response.set_cookie(
                key = 'visitedproduct'+str(product_id), value='T', max_age = EXPIRED_TIME
            )
        return response

'''
(1) 카테고리 - 맨 상단에 카테고리들 (좌우 스크롤) 모두 뿌려줌
(2) 인기 상품 - 구독자 수 기반 인기 상품 출력 (구독자 수가 많을 수록 인기 상품)
(3) 신규 상품 - 등록 날짜가 일주일 이내인 상품들 추천
'''
# url : /consumer/home/
class HomeView(APIView):
    def get(self, request):
        categories = Category.objects.all()
        popular_products = Product.objects.all().order_by('-num_of_subscribers')
        new_products = Product.objects.all().order_by('-update_date')

        
        PRODUCT_NUM = min(Product.objects.count(), STANDARD_NUM_OF_PRODUCTS) # 현재 Product 갯수가 NUM_OF_PRODUCTS (10) 보다 적을 때
        popular_products = popular_products[:PRODUCT_NUM] # 내림차순 구독자 수
        new_products = new_products[:PRODUCT_NUM] # 내림차순 update 기준 (-id도 가능)

        categories_data = CategoryListSerializer(categories, many=True).data
        popular_products_data = ProductListSerializer(popular_products, many=True).data
        new_products_data = ProductListSerializer(new_products, many=True).data
        return Response({
                'categories':categories_data, 
                'popular_products':popular_products_data, 
                'new_products':new_products_data,
            }, status=status.HTTP_200_OK)

''' legacy code 
def list(self, request):
    category_id = request.query_params['category']
    if not category_id.isdigit():
        return Response({'message':'Params is invalid'}, status.HTTP_400_BAD_REQUEST)

    product_data = Product.objects.filter(category_id=category_id)
    if len(product_data) == 0:
        return Response({'message':'There are no products in this category'}, status.HTTP_200_OK)

    ProductSerializer_data = ProductListSerializer(product_data, many=True).data
    return Response(ProductSerializer_data, status.HTTP_200_OK)

    # serializer = UserSerializer(queryset, many=True)
    # return Response(serializer.data)
'''
